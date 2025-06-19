'''
monkey logger that keeps track of what and when you screwed your data.
'''
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

class Wood:
    """
    Of course you have logs from a Wood! 

    Logger that writes to dataset directory
    """
    
    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)
        if not self.data_path.exists():
            raise FileNotFoundError(f'Trying to create logging in not existing folder: {self.data_path}')
        self.log_file = self.data_path / "processing.log"
        
        # ensure directory exists
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # setup logger
        self.logger = logging.getLogger(f"log_{id(self)}")  # unique per instance
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # file handler
        handler = logging.FileHandler(self.log_file, mode='a')
        formatter = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def start(self, step: str, details: str = None) -> None:
        msg = f"START: {step}"
        if details:
            msg += f" ({details})"
        self.logger.info(msg)
    
    def done(self, step: str, details: str = None) -> None:
        msg = f"DONE:  {step}"
        if details:
            msg += f" ({details})"
        self.logger.info(msg)
    
    @contextmanager
    def log(self, step: str, details: str = None):
        """Context manager that logs start/done automatically"""
        start_time = datetime.now()
        self.start(step, details)
        try:
            yield
        finally:
            duration = datetime.now() - start_time
            duration_str = f"{duration.total_seconds():.2f}s"
            self.done(step, duration_str)

# usage
# 
# wood = Wood(data_path)
# 
# with wood.log("loading_data"):
#    # your processing code here
#    ...
# 
# with wood.log("feature_extraction", "extracting 42 features"):
#    # processing code
#    ...