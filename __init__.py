import logging

logging.basicConfig(filename='exemple.log', encoding='utf-8', level=logging.DEBUG)
logging.debug('\nlog debug...\n')
logging.info('\nlog info...\n')
logging.warning('\nlog warning...\n')
logging.error('\nlog error...\n')