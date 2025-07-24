from ammonkey import (
    ExpNote, DAET, Path,
    iter_notes,
    getUnprocessedDlcData,
    AniposeProcessor,
    ColorLoggingFormatter
)
from itertools import tee

import logging
lg = logging.getLogger(__name__)
lg.setLevel(logging.DEBUG)
lg.handlers.clear()
handler = logging.StreamHandler()
handler.setFormatter(ColorLoggingFormatter())
lg.addHandler(handler)
lg.info('test')

def main() -> None:
    p = Path(r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025')
    ni1, ni2 = tee(iter_notes(p))

    need_anipose: dict[str, list[str]] = {}
    for n in ni1:
        date = n.date
        if not n.sync_path.exists():
            lg.warning(f'\033[33m{n} has no synced vid folder!\033[0m')
            continue
        udd = getUnprocessedDlcData(data_path=n.data_path)
        if udd:
            need_anipose[date] = udd

    lg.info('\033[7mdata needing anipose\033[0m')

    for date, list_model_sets in need_anipose.items():
        lg.info(f'{date}:')
        for ms in list_model_sets:
            lg.info(f'\t- {ms}')

if __name__ == '__main__':
    main()