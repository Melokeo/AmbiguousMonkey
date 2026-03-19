'''fake shutil and subprocess for testing'''

import shutil

class FakeShutil:
    @staticmethod
    def copy(src, dst):
        print(f'FakeShutil.copy({src}, {dst})')
        return dst

    @staticmethod
    def copytree(src, dst):
        print(f'FakeShutil.copytree({src}, {dst})')
        return dst

    @staticmethod
    def rmtree(path):
        # you do want to rm even in fake mode to avoid cluttering temp dirs
        print(f'FakeShutil.rmtree({path})')
        shutil.rmtree(path, ignore_errors=True)

class FakeSubprocess:
    @staticmethod
    def run(command, shell, capture_output, text):
        print(f'FakeSubprocess.run({command})')
        class Result:
            returncode = 0
            stdout = 'Fake output'
            stderr = ''
        return Result()