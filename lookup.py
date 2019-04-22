import collections 

def get_val_from_range(lookup, input):
    '''
    lookup: dictionary 
    input: float 
    
    For working principle, see below tests    
    '''
    lookup_sorted = collections.OrderedDict(sorted(lookup.items(), key=lambda t: float(t[0])))
    val = None
    for _range in lookup_sorted:
        val = lookup_sorted[_range]
        if float(input) > float(_range):
            continue 
        break 
    return val 

mytable = {
    1: 0.25,
    1.1: 0.28,
    3: 0.33,
    5: 0.42,
    999: 0.5
}
        
assert get_val_from_range(mytable, 0.1) == 0.25
assert get_val_from_range(mytable, 0.99) == 0.25
assert get_val_from_range(mytable, 1) == 0.25
assert get_val_from_range(mytable, 1.01) == 0.28
assert get_val_from_range(mytable, 1.09) == 0.28
assert get_val_from_range(mytable, 1.2) == 0.33
assert get_val_from_range(mytable, 2.5) == 0.33
assert get_val_from_range(mytable, 4) == 0.42
assert get_val_from_range(mytable, 40) == 0.5
assert get_val_from_range(mytable, 1000) == 0.5
