import logging

class ColorLoggingFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[2;36mD\033[0m',     # Cyan dim
        'INFO': '\033[0mI\033[0m',      # Green no, white
        'WARNING': '\033[33mW\033[0m',   # Yellow
        'ERROR': '\033[31mE\033[0m',     # Red
        'CRITICAL': '\033[41mC\033[0m',  # Red background
    }
    COLORS_NOTAIL = {       # used when coloring whole line
        'DEBUG': '\033[2;36mD',     # Cyan dim
        'INFO': '\033[0mI',      # Green no, white
        'WARNING': '\033[33mW',   # Yellow
        'ERROR': '\033[31mE',     # Red
        'CRITICAL': '\033[41mC',  # Red background
    }
    def format(self, record):
        level = self.COLORS_NOTAIL.get(record.levelname, record.levelname[0])
        name = f'{record.name.split(".")[-1]:<12}'  # fixed width for alignment
        return f'{level} {name} {record.getMessage()}' + '\033[0m'
    
def set_colored_logger(name: str):
    lg = logging.getLogger(name)
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    lg.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(ColorLoggingFormatter())
    lg.addHandler(handler)
    return lg