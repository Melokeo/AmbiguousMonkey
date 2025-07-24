import logging

class ColorLoggingFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36mD\033[0m',     # Cyan
        'INFO': '\033[32mI\033[0m',      # Green
        'WARNING': '\033[33mW\033[0m',   # Yellow
        'ERROR': '\033[31mE\033[0m',     # Red
        'CRITICAL': '\033[41mC\033[0m',  # Red background
    }
    def format(self, record):
        level = self.COLORS.get(record.levelname, record.levelname[0])
        name = f'{record.name:<12}'  # fixed width for alignment
        return f'{level} {name} {record.getMessage()}'