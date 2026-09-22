"""Lossless, chunk-addressed build reference for emulator pixel verification."""
import json
from PIL import Image


class WorldReference:
    def __init__(self, directory):
        self.layout=json.loads((directory/'reference-layout.json').read_text())
        self.atlas=Image.open(directory/'reference-atlas.png').convert('RGB')

    def getpixel(self, position):
        x,y=position
        if not (0<=x<self.layout['width'] and 0<=y<self.layout['height']):
            raise IndexError(position)
        chunk=self.layout['chunk_ids'][(y//256)*self.layout['columns']+x//256]
        columns=self.layout['atlas_columns']
        return self.atlas.getpixel((chunk%columns*256+x%256,chunk//columns*256+y%256))
