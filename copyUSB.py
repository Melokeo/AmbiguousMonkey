'''
Identifying MTP/PTP device and copying data
'''

from datetime import datetime
import os, win32com.client

def copyVidsFromCam(cam_name, date, base):
    shell = win32com.client.Dispatch("Shell.Application")
    this_pc = shell.Namespace(17)
    os.makedirs(base, exist_ok=True)

    c = 0
    for i in this_pc.Items():
        if cam_name in i.Name:
            c += 1
            ddest = os.path.join(base, f'FX43A_i')
            os.makedirs(ddest, exist_ok=True)

            f1 = i.GetFolder
            for sub1 in f1.Items():
                if sub1.IsFolder:
                    f2 = f1.GetFolder
                    for sub2 in f2.Items():
                        if sub2.IsFolder and date in sub2.Name:
                            shell.Namespace(ddest).CopyHere(sub2, 20)

if __name__=='__main__':
    date = datetime.today().strftime('%Y-%m-%d')
    copyVidsFromCam('FX43A', date, 'C:/Users/rnel/Videos/Copied from cam')