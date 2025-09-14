import itertools
from db import *

one_chunk = 15

bitly_allowed = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 
    'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 
    'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 
    'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 
    'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 
    'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', 
    '8', '9', '-', '_'
]

sid_allowed = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 
    'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 
    'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 
    'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 
    'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 
    'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', 
    '8', '9', '-', '_'
]

shorturl_allowed = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 
    'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 
    'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 
    'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 
    'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 
    'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', 
    '8', '9'
]



def generate_bitly():
    pending = unresolved_retrieve()
    if pending != None:
        return pending
    last_index = get_state('bitly')
    current_index = last_index
    result = []

    for length in range(1, 25):
        combinations = itertools.product(bitly_allowed, repeat=length)

        # Slice only the remaining needed items
        for combo in itertools.islice(combinations, current_index, current_index + one_chunk - len(result)):
            result.append(''.join(combo))

        if len(result) >= one_chunk:
            break

    current_index += len(result)
    update_state('bitly', current_index)  # Update DB once
    result = [f"https://bit.ly/{item}" for item in result]
    return result


def generate_sid():
    pending = unresolved_retrieve()
    if pending != None:
        return pending
    last_index = get_state('sid')
    current_index = last_index
    result = []

    for length in range(1, 48):
        combinations = itertools.product(sid_allowed, repeat=length)

        for combo in itertools.islice(combinations, current_index, current_index + one_chunk - len(result)):
            result.append(''.join(combo))

        if len(result) >= one_chunk:
            break

    current_index += len(result)
    update_state('sid', current_index)  # Update DB once
    result = [f"https://s.id/{item}" for item in result]
    return result

def generate_shorturl():
    pending = unresolved_retrieve()
    if pending != None:
        return pending
    last_index = get_state('shorturl')
    current_index = last_index
    result = []

    # For lengths from 1 to 10
    for length in range(5, 22):
        combinations = itertools.product(shorturl_allowed, repeat=length)
        
        # Slice only the block we need
        for combo in itertools.islice(combinations, current_index, current_index + one_chunk - len(result)):
            result.append(''.join(combo))
       
    current_index += len(result)  # Update the index after generating all items
    update_state('shorturl', current_index)  # Update DB once

    result = [f"https://shorturl.at/{item}" for item in result]

    return result

