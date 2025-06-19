'''
Identifying MTP/PTP device and copying data
'''

from datetime import datetime
import os, win32com.client, shutil

def copyVidsFromCam(cam_name: str, date: str, base: str) -> None:
    shell = win32com.client.dynamic.Dispatch("Shell.Application")
    this_pc = shell.Namespace(17)
    this_pc = win32com.client.gencache.EnsureDispatch(this_pc)
    print(this_pc)
    os.makedirs(base, exist_ok=True)

    c = 0
    for i in this_pc.Items():
        if cam_name in i.Name:
            c += 1
            # ddest = os.path.join(base, f'{cam_name}_{date}')
            ddate = date.replace('-', '')
            ddest = os.path.join(base, f'{cam_name}_{ddate}_{c}')
            os.makedirs(ddest, exist_ok=True)

            f1 = i.GetFolder
            for sub1 in f1.Items():
                if sub1.IsFolder:
                    print(f1, sub1)
                    f2 = sub1.GetFolder
                    for sub2 in f2.Items():
                        if sub2.IsFolder and date in sub2.Name:
                            print(f'Hit {date} in {cam_name} #{c-1}')
                            f3 = sub2.GetFolder
                            for sub3 in f3.Items():
                                print(sub3.Path, ddest)
                                #shutil.copy(sub3.Path, ddest)
                                print('Copying...')
                                shell.Namespace(ddest).CopyHere(sub2, 16 | 512 | 1024)
                            

    # this_pc.Quit()

if __name__=='__main__':
    date = datetime.today().strftime('%Y-%m-%d')
    month = datetime.today().strftime('%m')
    year = datetime.today().strftime('%Y')
    print(date)
    copyVidsFromCam('FDR-AX43A', date, r'C:\Users\rnel\Videos\Copied from cam')
    # copyVidsFromCam('FDR-AX43A', date, fr'P:\projects\monkeys\Chronic_VLL\DATA_RAW\Pici\{year}\{month}\{date}')

# then: 1. auto-rename according to xlsx; 2. arrangement for trial vids; 3. arg. & send for calib.