import subprocess
import tempfile
import os
import re
from typing import Tuple, Optional

class LuaValidator:
    @staticmethod
    def clean_code(code: str) -> str:
        cleaned = re.sub(r'[^\x20-\x7E\n\r\t]', '', code)  # сначала вырезаем все не-ASCII
        return cleaned

    @staticmethod
    def check_syntax(code: str) -> Tuple[bool, str]:
        code = LuaValidator.clean_code(code)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False, encoding='utf-8') as f:
            f.write(code)
            tmpfile = f.name
        try:
            result = subprocess.run(['luac', '-p', tmpfile], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return True, "Syntax OK"
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)
        finally:
            os.unlink(tmpfile)

    @staticmethod
    def run_luacheck(code: str) -> Tuple[bool, str]:
        code = LuaValidator.clean_code(code)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False, encoding='utf-8') as f:
            f.write(code)
            tmpfile = f.name
        try:
            result = subprocess.run(['luacheck', '--no-color', tmpfile], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True, "Luacheck passed"
            else:
                return False, result.stdout.strip() or result.stderr.strip()
        except FileNotFoundError:
            return True, "luacheck not installed, skip"
        except Exception as e:
            return False, str(e)
        finally:
            os.unlink(tmpfile)

    @staticmethod
    def run_tests(code: str, test_input: Optional[str] = None, expected_output: Optional[str] = None) -> Tuple[bool, str]:
        if test_input is None or expected_output is None:
            return True, "No tests provided"
        code = LuaValidator.clean_code(code)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False, encoding='utf-8') as f:
            f.write(code)
            tmpfile = f.name
        try:
            proc = subprocess.run(['lua', tmpfile], input=test_input, capture_output=True, text=True, timeout=5)
            output = proc.stdout.strip()
            if output == expected_output.strip():
                return True, "Tests passed"
            else:
                return False, f"Expected '{expected_output}', got '{output}'"
        except Exception as e:
            return False, str(e)
        finally:
            os.unlink(tmpfile)