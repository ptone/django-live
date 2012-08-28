color_names = {
'red':(0, 19),
'orange':(20, 49),
'yellow':(50, 69),
'lime':(70, 84),
'green':(85, 170),
'aqua':(171,191),
'blue':(192, 264),
'violet':(265, 289),
'purple':(290, 329),
'red_':(330, 360)
    }

saturations = {

'drab':(0, 29),
'faded':(30, 64),
}

"""
0
ffffff
 
29
d0ffb5
 
faded	
30
cfffb3
 
64
98ff5c
 
rich	
65
96ff59
 
84
77ff29
 
pure	
85
76ff26
 
100
5eff00
 
descriptor	v start	v end
dark	
0
000000
 
32
1e5200
 
medium	
33
1f5400
 
65
3da600
 
bright	
66
3ea800
 
100
5eff00
"""

hue_map = {}

for name, hue_range in color_names.items():
    print name, hue_range
    for hue in range(hue_range[0], hue_range[1]+1):
        hue_map[hue] = name.rstrip("_")

