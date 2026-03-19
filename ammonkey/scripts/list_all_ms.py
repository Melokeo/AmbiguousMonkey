from pathlib import Path
from ammonkey.core.dlcCollector import searchModelSets

data_base = Path(r'P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025')
msa = []
msd = []
for mon in data_base.glob('*'):
    if not mon.is_dir():
        continue
    for date in mon.glob('*'):
        if not date.is_dir():
            continue
        model_sets_ani = searchModelSets(date / 'anipose')

        for daet in (date / 'SynchronizedVideos').glob('*'):
            if not daet.is_dir():
                continue
            model_sets_dlc = searchModelSets(daet / 'dlc')
            if model_sets_dlc:
                for ms in model_sets_dlc:
                    msd.append(f'{daet.name}\t{ms}')

        if model_sets_ani:
            for ms in model_sets_ani:
                msa.append(f'{mon.name}\t{date.name}\t{ms}')

msa = sorted(msa)
msd = sorted(msd)

print('DLC MS:')
for ms in msd:
    print(ms)

print('\n\nAnipose MS:')
for ms in msa:
    print(ms)
