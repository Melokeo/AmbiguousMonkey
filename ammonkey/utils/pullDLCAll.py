'''
Search for un-processed pull tasks and run DLC
'''

from ambiguousmonkey.monkeyUnityv1_8 import readExpNote, Task, task_match, runDLC
from pathlib import Path
import os

import contextlib
import io
from estimateDLCTime import *

t = Task.Pull

p = r'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\2025'
p = Path(p)
vp = []

def cleanSkipFile(p:str):
    P = Path(p)
    SD = P / '.skipDLC'
    flag = False
    for i in P.rglob('*.h5'):
        flag = True

    if not flag and SD.exists():
        os.remove(str(SD))
        print(f'Cleaned skipDLC in {os.path.basename(p)}')

print(task_match[t])

bypass = False
if not bypass:
    for f in p.rglob('PICI_????????.xlsx'):
        pp = os.path.dirname(f)

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                df = readExpNote(pp)
        except KeyError as ke:
            print(f'KeyError reading {os.path.basename(pp)}', end='; ', flush=True)
            continue
        else:
            pass
            # print(f'Read {os.path.basename(pp)}')

        fl = False
        for _, r in df.iterrows():
            if any(x in str(r['Experiment']).lower() for x in task_match[t]):
                fl = True
        if not fl:
            print(f'Skipped {os.path.basename(pp)}', end='; ', flush=True)
            continue
        else: 
            print(f'Hit {os.path.basename(pp)}', end='; ', flush=True)

        pdata = Path(pp.replace('DATA_RAW', 'DATA')) / 'SynchronizedVideos'
        if pdata.exists():
            for e in pdata.rglob('????????-Pici*.mp4'):
                eb = os.path.basename(e)
                ef = os.path.dirname(e)
                # cleanSkipFile(ef)
                if any(x in eb.lower() for x in task_match[t]):
                    if not os.path.exists(os.path.join(ef, '.skipDLC')):
                        vp.append(os.path.dirname(ef)) if not os.path.dirname(ef) in vp else None
                        # Omitted L/R in path
                        print(f'1 set in {os.path.basename(pp)}', end='! ', flush=True)
            print('')
else:
    vp = [
        'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\02\\20250224\\SynchronizedVideos\\20250224-Pici-Pull-3', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\02\\20250224\\SynchronizedVideos\\20250224-Pici-Pull-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\02\\20250219\\SynchronizedVideos\\20250219-Pici-Pull-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\02\\20250219\\SynchronizedVideos\\20250219-Pici-Pull-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\02\\20250219\\SynchronizedVideos\\20250219-Pici-Pull-3', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-6', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-10', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-7', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-5', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-9', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-11', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250418\\SynchronizedVideos\\20250418-Pici-Pull-Big Sphere-8', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250409\\SynchronizedVideos\\20250409-Pici-Pull-Big Sphere-7', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250409\\SynchronizedVideos\\20250409-Pici-Pull-Big Sphere-8', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250407\\SynchronizedVideos\\20250407-Pici-Pull -Constrained-16', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250407\\SynchronizedVideos\\20250407-Pici-Pull -Constrained-13', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250407\\SynchronizedVideos\\20250407-Pici-Pull -Constrained-15', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\04\\20250407\\SynchronizedVideos\\20250407-Pici-Pull -Constrained-12', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250331\\SynchronizedVideos\\old ver\\20250331-Pici-Pull-Big Sphere-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull Sphere big-4', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull cylinder-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull cylinder-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull Sphere big-5', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull Sphere big-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull Sphere big-3', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250320\\SynchronizedVideos\\20250320-Pici-Pull Sphere big-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereBig-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereSmall-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereBig-3', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereBig-5', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereSmall-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereBig-4', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereBig-6', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250325\\SynchronizedVideos\\20250325-Pici-Pull-SphereBig-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250304\\SynchronizedVideos\\20250304-Pici-Pull-3', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250304\\SynchronizedVideos\\20250304-Pici-Pull-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250304\\SynchronizedVideos\\20250304-Pici-Pull-4', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250304\\SynchronizedVideos\\20250304-Pici-Pull-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250311\\SynchronizedVideos\\20250311-Pici-Pull-3', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250311\\SynchronizedVideos\\20250311-Pici-Pull-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250311\\SynchronizedVideos\\20250311-Pici-Pull-2', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250319\\SynchronizedVideos\\20250319-Pici-Pull-Sphere-1', 'P:\\projects\\monkeys\\Chronic_VLL\\DATA\\Pici\\2025\\03\\20250319\\SynchronizedVideos\\20250319-Pici-Pull-Sphere-2'
    ]

print(vp)
print(f'=====\nFound {len(vp)} sets of unprocessed tasks')

estm = True
if estm:
    print('Now estimating processing time.')
    spd = 21.65
    dur = printDLCTime(vp,speed=spd)
    print(f'Average vid length: {format_duration(dur*spd/119.88/len(vp)/4)}')
    print(f'Estimated total time: {format_duration(dur)}')
    print(f'Estimated finish time: {add_time(dur)}')
else:   
    print(f'Estimated time with ~36000 frames per vid: {round(4*36000*len(vp)/21/60/60, 1)} hrs')

input('Confirm DLC >>> ')

try:
    runDLC(vp, shuffle={'L':7, 'R':7}, side=['L', 'R'])
except Exception as e:
    print(e)


