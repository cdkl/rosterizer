import logging

def parse_name(full_name):
    first_name = ''
    last_name = ''
    try:
        last_name, first_name = full_name.split(', ')
    except ValueError:
        logging.warning(f'Could not parse name: {full_name}')
    finally:
        return first_name,last_name
