import logging
import re
from typing import TextIO
import textwrap
import flet as ft

class FletLogHandler(logging.Handler):
    def __init__(self, text_control: ft.Text):
        super().__init__()
        self.text_control = text_control
        # ansi color codes to flet colors mapping
        self.color_map = {
            '30': ft.Colors.BLACK, '31': ft.Colors.RED, '32': ft.Colors.GREEN,
            '33': ft.Colors.YELLOW, '34': ft.Colors.BLUE, '35': ft.Colors.PURPLE,
            '36': ft.Colors.CYAN, '37': ft.Colors.WHITE,
            '90': ft.Colors.GREY_400, '91': ft.Colors.RED_300, '92': ft.Colors.GREEN_300,
            '93': ft.Colors.YELLOW_300, '94': ft.Colors.BLUE_300, '95': ft.Colors.PURPLE_300,
            '96': ft.Colors.CYAN_300, '97': ft.Colors.WHITE
        }
        self.font_family = 'Consolas'
    
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        spans = self._parse_ansi(msg)
        
        # add to existing spans or create new
        if self.text_control.spans:
            self.text_control.spans.extend(spans)
        else:
            self.text_control.spans = spans
        
        self.text_control.update()
    
    def _parse_ansi(self, text: str) -> list[ft.TextSpan]:
        # regex for ansi escape sequences
        ansi_pattern = r'\033\[([0-9;]+)m'
        spans = []
        last_end = 0
        current_style = ft.TextStyle(font_family=self.font_family)
        
        for match in re.finditer(ansi_pattern, text):
            # add text before this escape sequence
            if match.start() > last_end:
                plain_text = text[last_end:match.start()]
                if plain_text:
                    spans.append(ft.TextSpan(plain_text, current_style))
            
            # parse escape codes
            codes = match.group(1).split(';')
            current_style = self._apply_codes(current_style, codes)
            last_end = match.end()
        
        # add remaining text
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                spans.append(ft.TextSpan(remaining + '\n', current_style))
        
        return spans
    
    def _apply_codes(self, style: ft.TextStyle, codes: list[str]) -> ft.TextStyle:
        new_style = ft.TextStyle(
            color=style.color,
            weight=style.weight,
            italic=style.italic,
            font_family=self.font_family,
        )
        
        for code in codes:
            if code == '0':  # reset
                new_style = ft.TextStyle(font_family=self.font_family)
            elif code == '1':  # bold
                new_style.weight = ft.FontWeight.BOLD
            elif code == '3':  # italic
                new_style.italic = True
            elif code in self.color_map:  # color
                new_style.color = self.color_map[code]
        
        return new_style

class ColorLoggingFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36mD\033[0m',     # Cyan
        'INFO': '\033[0mI\033[0m',      # White
        'WARNING': '\033[33mW\033[0m',   # Yellow
        'ERROR': '\033[31mE\033[0m',     # Red
        'CRITICAL': '\033[41mC\033[0m',  # Red background
    }
    def __init__(self, fmt=None, datefmt=None, style='%', *, width=120):
        super().__init__(fmt, datefmt, style)   #type:ignore
        self.width = width # total character width for wrapping

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Removes ANSI escape sequences from a string."""
        return re.sub(r'\033\[([0-9;]*)m', '', text)
    
    def format(self, record: logging.LogRecord) -> str:
        level = self.COLORS.get(record.levelname, record.levelname[0])
        name = f'{record.name.split(".")[-1]:<10}'
        time = self.formatTime(record, '[%H:%M]') 
        
        # 1. Create the prefix and calculate its visual length
        prefix = f'{time} {name} {level} '
        prefix_visual_len = len(self._strip_ansi(prefix))

        # 2. Create a TextWrapper for hanging indents
        wrapper = textwrap.TextWrapper(
            width=self.width,
            initial_indent=prefix,
            subsequent_indent=' ' * prefix_visual_len,
            replace_whitespace=False, # Preserve existing newlines in message
            break_on_hyphens=False
        )

        # 3. Wrap the message
        # Note: This simple implementation assumes the core message does not contain ANSI codes.
        # If it did, `textwrap` would miscalculate string lengths.
        message = record.getMessage()
        return wrapper.fill(message)

def get_flet_logger(name: str, width:int = 80) -> logging.Logger:   # wip
    lg = logging.getLogger(name)
    return lg

def main(page: ft.Page):
    log_display = ft.Text(spans=[], selectable=True)
    
    # setup logging
    logger = logging.getLogger()
    flet_handler = FletLogHandler(log_display)
    flet_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(flet_handler)
    logger.setLevel(logging.INFO)
    
    page.add(
        ft.Column([
            ft.Text("Log Output:"),
            ft.Container(
                content=log_display,
                bgcolor=ft.Colors.BLACK,
                padding=10,
                border_radius=5,
                height=400,
                width=680
            )
        ])
    )
    
    # test with colored output
    logger.info("\033[31mRed error message\033[0m")
    logger.info("\033[32mGreen success\033[0m \033[1mbold text\033[0m")

if __name__=='__main__':
    ft.app(main)