# /src/parchive/parchive_commander.py
from pathlib import Path

class Parchive2Commander:
    def __init__(self, bin_file_path: Path) -> None:
        self._bin_path_str: str = str(bin_file_path)
    
    def build_create_command(self, input_file_path_str: str, output_file_path_str: str, redundancy: int, base_file_path_str: str, memory_limit: int = 1024) -> list[str]:
        if not input_file_path_str:
            raise ValueError('입력 파일의 경로는 필수입니다.')

        if not output_file_path_str:
            raise ValueError('출력 파일의 경로는 필수입니다.')
            
        if not base_file_path_str:
            raise ValueError('기준 경로는 필수입니다.')
        
        cmd: list[str] = []
        cmd.append(self._bin_path_str)
        cmd.append("c")
        cmd.append(f"-r{redundancy}")
        cmd.append(f"-m{memory_limit}")
        cmd.append(f"-B{base_file_path_str}")
        cmd.append(output_file_path_str)
        cmd.append(input_file_path_str)

        return cmd