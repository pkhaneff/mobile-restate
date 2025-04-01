import re
import subprocess
from typing import List
from log import Log

class GitUtils:

    @staticmethod
    def split_diff_into_chunks(diff_text):
        """Chia một diff lớn thành danh sách các diff chunk nhỏ hơn."""
        return re.split(r"(diff --git.*?)(?=diff --git|\Z)", diff_text, flags=re.DOTALL)[1::2]
    
    @staticmethod
    def __run_subprocess(command):
        Log.print_green(command)
        result = subprocess.run(command, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        if result.returncode == 0:
            return result.stdout
        else:
            Log.print_red(command)
            raise Exception(f"Error running {command}: {result.stderr}")

    @staticmethod
    def is_sha(ref: str) -> bool:
        return re.match(r'^[0-9a-f]{40}$', ref.lower()) is not None

    @staticmethod
    def get_remote_name() -> str:
        command = ["git", "remote", "-v"]
        result = GitUtils.__run_subprocess(command)
        lines = result.strip().splitlines()
        return lines[0].split()[0] if lines else "origin"

    @staticmethod
    def get_last_commit_sha(file: str) -> str:
        command = ["git", "log", "-1", "--format=%H", "--", file]
        result = GitUtils.__run_subprocess(command)
        lines = result.strip().splitlines()
        return lines[0] if lines else ""

    @staticmethod
    def get_diff_files(base_ref: str, head_ref: str) -> List[str]:
        remote_name = GitUtils.get_remote_name()
        base = base_ref if GitUtils.is_sha(base_ref) else f"{remote_name}/{base_ref}"
        head = head_ref if GitUtils.is_sha(head_ref) else f"{remote_name}/{head_ref}"

        command = ["git", "diff", "--name-only", base, head]
        result = GitUtils.__run_subprocess(command)
        return result.strip().splitlines()

    @staticmethod
    def get_diff_in_file(base_ref: str, head_ref: str, file_path: str) -> str:
        remote_name = GitUtils.get_remote_name()
        base = base_ref if GitUtils.is_sha(base_ref) else f"{remote_name}/{base_ref}"
        head = head_ref if GitUtils.is_sha(head_ref) else f"{remote_name}/{head_ref}"

        command = ["git", "diff", base, head, "--", file_path]
        return GitUtils.__run_subprocess(command)
