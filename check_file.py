import os
print('dynamic_field_detector.py exists:', os.path.exists('dynamic_field_detector.py'))
print('Current directory:', os.getcwd())
print('Files in directory:')
for f in os.listdir('.'):
    if 'dynamic' in f or 'detector' in f:
        print(f'  {f}')
