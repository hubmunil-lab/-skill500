"""Self-created abstract transparent graphics, explicitly NOT food photographs."""
from io import BytesIO
from PIL import Image, ImageDraw
from .engine import ROOT


def create_fixtures():
    folder=ROOT/'artifacts/phase2-fixtures'
    folder.mkdir(parents=True,exist_ok=True)
    for i,size in enumerate([(640,480),(460,640),(440,900)],1):
        im=Image.new('RGBA',size,(0,0,0,0))
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((25,25,size[0]-25,size[1]-25),radius=30,fill=(207,216,193,220),outline='#827655',width=4)
        for y in range(70,size[1]-50,60):d.line((50,y,size[0]-50,y),fill=(143,154,131,180),width=2)
        d.text((55,42),f'PHOTO SLOT {i} / TEST ONLY',fill='#38442e',font_size=22)
        d.text((55,size[1]-65),'NOT A FOOD PHOTO',fill='#38442e',font_size=22)
        data=BytesIO();im.save(data,format='PNG')
        target=folder/f'placeholder-{i}.png'
        if target.exists() and target.read_bytes()!=data.getvalue():
            raise ValueError('Refusing to overwrite existing different fixture: '+str(target))
        if not target.exists():target.write_bytes(data.getvalue())
