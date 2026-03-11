# /src/manager/scheduler.py
import time
import queue
from pathlib import Path
from typing import Optional
from queue import Queue
from threading import Thread, Event

from src.core.config import settings
from src.core.logger import logger
from src.hardware.engineer import monitoring
from src.transcode.transcode_engine import TranscodeEngine
from src.parchive2.parchive2_engine import Parchive2Engine
from src.database.repository import MediaRepository
from src.model.contents import (
    GPUstatus, TaskConfig, Par2Config, WorkPayload
)

class Scheduler:
    def __init__(self, transcode_engine: Optional[TranscodeEngine] = None, parchive2_engine: Optional[Parchive2Engine] = None) -> None:
        self.is_running: bool = False
        self.task_queue: Queue[WorkPayload] = Queue()

        self.transcode_engine: TranscodeEngine = transcode_engine or TranscodeEngine()
        self.parchive2_engine: Parchive2Engine = parchive2_engine or Parchive2Engine()
        self.active_threads: list[Thread] = []

        self.cancel_event: Event = Event()
        self.transcode_engine._cancel_event = self.cancel_event
        self.parchive2_engine._cancel_event = self.cancel_event

        gpu_count: int = monitoring.get_gpu_count()
        self.gpu_status: dict[int, bool] = {index: False for index in range(gpu_count)}

        logger.info(f'감지된 GPU {gpu_count}개를 기준으로 Scheduler를 초기화 합니다: {self.gpu_status}')

    def _work_thread(self, select_gpu: int, work_payload: WorkPayload) -> None:
        is_gpu_released: bool = False
        work_start_time: float = time.time()
        logger.info(f'GPU{select_gpu}의 스레드 작업을 시작합니다: {work_payload.input_path}')

        MediaRepository.update_pipeline_status(work_payload.media_id, 'Encoding', 0)

        try:
            task_config: TaskConfig = TaskConfig(
                index=select_gpu, 
                input_path=str(work_payload.input_path), 
                output_path=str(work_payload.output_path),
                video_codec=work_payload.video_codec, 
                video_cq=work_payload.video_cq, 
                video_preset=work_payload.video_preset, 
                video_cd=work_payload.video_cd,
                audio_codec=work_payload.audio_codec, 
                audio_bit=work_payload.audio_bit,
                video_stream=work_payload.video_stream, 
                audio_stream=work_payload.audio_stream,
                verify_vmaf=work_payload.verify_vmaf, 
                create_par2=work_payload.create_par2
            )

            def _transcode_progress(percent: int) -> None:
                logger.debug(f'GPU{select_gpu} 진행률: {percent}%')
                if percent % 5 == 0:
                    MediaRepository.update_pipeline_status(work_payload.media_id, 'Encoding', percent)

            is_successed: bool = self.transcode_engine.engine_run(task_config, _transcode_progress)

            self.gpu_status[select_gpu] = False
            is_gpu_released = True
            logger.info(f'GPU{select_gpu}의 인코딩이 종료되어 자원을 대기열로 반환합니다.')

            if self.cancel_event.is_set():
                MediaRepository.update_pipeline_status(work_payload.media_id, 'Canceled', 0)
                return
                
            if not is_successed:
                MediaRepository.update_pipeline_status(work_payload.media_id, 'Failed', 0)
                return

            if work_payload.verify_vmaf and not self.cancel_event.is_set():
                MediaRepository.update_pipeline_status(work_payload.media_id, 'Evaluating', 0)
                logger.info(f'VMAF 품질 검증을 시작합니다: {work_payload.output_path}')

                vmaf_score: float = self.transcode_engine.verify_vmaf_process(
                    original_file_path=str(work_payload.input_path), 
                    transcoded_file_path=str(work_payload.output_path), 
                    progress_callback=lambda percent: logger.debug(f'VMAF 진행률: {percent}%')
                )

                if self.cancel_event.is_set():
                    MediaRepository.update_pipeline_status(work_payload.media_id, 'Canceled', 0)
                    return

                MediaRepository.complete_evaluation(work_payload.media_id, vmaf_score)

                if vmaf_score >= settings.LOWEST_SCORE:
                    logger.info(f'VMAF 품질 검증 결과 {vmaf_score:.2f}점으로 충족합니다.')

                else:
                    logger.warning(f'VMAF 검증 결과 {vmaf_score:.2f}점으로 미달입니다.')

            if work_payload.create_par2 and not self.cancel_event.is_set():
                MediaRepository.update_pipeline_status(work_payload.media_id, 'Protecting', 0)
                logger.info(f'PAR2 데이터 생성을 시작합니다: {work_payload.output_path}')

                archive_dir: Path = settings.ARCHIVE_PATH / Path(work_payload.output_path).stem
                archive_dir.mkdir(parents=True, exist_ok=True)

                output_par2_path: Path = archive_dir / f"{Path(work_payload.output_path).name}.par2"

                par2_config: Par2Config = Par2Config(
                    input_path=str(work_payload.output_path), 
                    output_path=str(output_par2_path), 
                    redundancy=work_payload.redundancy
                )

                par2_success: bool = self.parchive2_engine.engine_run(par2_config, progress_callback=lambda percent: logger.debug(f'PAR2 진행률: {percent}%'))

                if self.cancel_event.is_set():
                    MediaRepository.update_pipeline_status(work_payload.media_id, 'Canceled', 0)
                    return

                if par2_success:
                    MediaRepository.complete_protection(work_payload.media_id)

                else:
                    MediaRepository.update_pipeline_status(work_payload.media_id, 'Failed', 0)

            elif not self.cancel_event.is_set():
                MediaRepository.update_pipeline_status(work_payload.media_id, 'Completed', 100)

            work_elapse_time: float = time.time() - work_start_time
            work_hours, work_remainder = divmod(work_elapse_time, 3600)
            work_minutes, work_seconds = divmod(work_remainder, 60)
            logger.info(f'스레드 작업을 모두 완료했습니다: {int(work_hours)}시간 {int(work_minutes)}분 {int(work_seconds)}초')

        except Exception as error:
            logger.error(f'스레드 작업 중 알 수 없는 오류가 발생했습니다: {error}')
            MediaRepository.update_pipeline_status(work_payload.media_id, 'Failed', 0)

        finally:
            if not is_gpu_released:
                self.gpu_status[select_gpu] = False

            self.task_queue.task_done()
            logger.info(f'작업 스레드를 완전히 종료합니다.')

    def _get_available_gpu(self) -> Optional[int]:
        gpu_count: int = monitoring.get_gpu_count()

        if gpu_count == 0:
            return None

        for index in range(gpu_count):
            if self.gpu_status.get(index, True):
                continue

            stat: Optional[GPUstatus] = monitoring.get_gpu_status(index)
            if stat and stat.is_safe:
                if stat.load < 20:
                    return index

        return None

    def _main_loop(self) -> None:
        while self.is_running:
            try:
                self.active_threads = [thread for thread in self.active_threads if thread.is_alive()]

                try:
                    payload: WorkPayload = self.task_queue.get(timeout=1.0)

                except queue.Empty:
                    continue

                select_gpu: Optional[int] = self._get_available_gpu()

                if select_gpu is not None:
                    self.gpu_status[select_gpu] = True
                    worker: Thread = Thread(
                        target=self._work_thread, 
                        kwargs={
                            "select_gpu": select_gpu,
                            "work_payload": payload
                        },
                        daemon=True
                    )
                    worker.start()
                    self.active_threads.append(worker)

                else:
                    self.task_queue.put(payload)
                    time.sleep(1)

            except Exception as error:
                logger.error(f'Scheduler의 메인 루프 진행 중 알 수 없는 오류가 발생했습니다: {error}')
                time.sleep(1)

    def start_scheduler(self) -> None:
        if self.is_running:
            return
        
        self.is_running = True
        self.cancel_event.clear()
        Thread(target=self._main_loop, daemon=True).start()
        logger.info('Scheduler를 시작합니다.')

    def stop_scheduler(self) -> None:
        self.is_running = False
        self.cancel_event.set()
        logger.info('Scheduler를 종료하고 진행 중인 모든 작업을 강제 취소합니다.')

    def add_task(self, work_payload: WorkPayload) -> None:
        self.task_queue.put(work_payload)
        logger.info(f'대기열에 작업을 추가합니다. (총 {self.task_queue.qsize()}개): {work_payload.input_path}')