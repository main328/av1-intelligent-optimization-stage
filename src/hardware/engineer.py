# /src/hardware/engineer.py
import atexit
import pynvml
import threading
from typing import Optional, Any

from src.core.logger import logger
from src.model.contents import GPUstatus

class Engineer:
    _instance: Optional['Engineer'] = None
    _instance_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'Engineer':
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(Engineer, cls).__new__(cls)
                cls._instance._init_nvml()

        return cls._instance
    def _init_nvml(self) -> None:
        self.initialized: bool = False

        try:
            pynvml.nvmlInit()

            self.initialized = True
            logger.info('NVML 라이브러리 초기화에 성공했습니다.')

            atexit.register(self._shutdown_nvml)

        except pynvml.NVMLError as error:
            logger.error(f'NVML 라이브러리 초기화에 실패했습니다: {error}')

        except Exception as error:
            logger.error(f'NVML 라이브러리 초기화 중 알 수 없는 오류가 발생했습니다: {error}')

    def _shutdown_nvml(self) -> None:
        if hasattr(self, 'initialized') and self.initialized:
            try:
                pynvml.nvmlShutdown()
                logger.info('NVML 라이브러리 반환에 성공했습니다.')

            except Exception as error:
                logger.error(f'NVML 라이브러리 반환 중 알 수 없는 오류가 발생했습니다: {error}')

    def get_gpu_count(self) -> int:
        if not self.initialized: 
            return 0

        with self._instance_lock:
            return int(pynvml.nvmlDeviceGetCount())

    def get_gpu_status(self, select_gpu: int) -> Optional[GPUstatus]:
        if not self.initialized: 
            return None

        with self._instance_lock:
            try:
                handle: Any = pynvml.nvmlDeviceGetHandleByIndex(select_gpu)
                temperature: int = int(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
                device_name: str = str(pynvml.nvmlDeviceGetName(handle))
                utilization: Any = pynvml.nvmlDeviceGetUtilizationRates(handle)
                memory_info: Any = pynvml.nvmlDeviceGetMemoryInfo(handle)
                logger.debug(f'GPU{select_gpu}의 상태 정보 획득에 성공했습니다.')

                return GPUstatus(
                    index=select_gpu,
                    name=device_name,
                    tmp=temperature,
                    load=int(utilization.gpu),
                    vram=int(utilization.memory),
                    vram_total=float(memory_info.total // (1024**2)),
                    vram_used=float(memory_info.used // (1024**2)),
                    vram_free=float(memory_info.free // (1024**2)),
                )

            except pynvml.NVMLError as error:
                logger.error(f'GPU({select_gpu})의 상태 정보 획득에 실패했습니다: {error}')
                return None

            except Exception as error:
                logger.error(f'GPU({select_gpu})의 상태 정보 획득 중 알 수 없는 오류가 발생했습니다: {error}')
                return None

monitoring: Engineer = Engineer()