"""Local sound audition, without launching the Scramble arcade game.

Run from tools/sound_capture or double-click Preview_Scramble_Sounds.bat.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scramble_audio import ONESHOTS,AMBIENTS,SOUNDS_DIR

def main():
    try:
        import pygame
        pygame.mixer.pre_init(frequency=48000,size=-16,channels=1,buffer=512)
        pygame.mixer.init()
    except Exception as exc:
        print('Audio device not available:',exc)
        return 1
    names=ONESHOTS+AMBIENTS
    try:
        while True:
            print('\n=== SCRAMBLE / MAME 1981 SOUND PREVIEW ===')
            for i,name in enumerate(names,1):
                print(f'{i:2}: {name.replace("_"," ")}')
            print(' 0: Exit')
            answer=input('Choose sound number: ').strip()
            if answer in ('0','q','quit','exit',''):
                break
            try:
                idx=int(answer)-1
                if not 0<=idx<len(names):raise ValueError
            except ValueError:
                print('Choose a listed number.');continue
            name=names[idx]
            path=SOUNDS_DIR/(name+'.wav')
            snd=pygame.mixer.Sound(str(path))
            pygame.mixer.stop()
            snd.play(loops=1 if name in AMBIENTS else 0)
            print(f'{name}: {snd.get_length():.2f}s.  Press Enter to stop.')
            input()
            pygame.mixer.stop()
    except (EOFError,KeyboardInterrupt):
        pass
    finally:
        pygame.mixer.quit()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
