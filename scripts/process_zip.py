import zipfile
import numpy
import utils

monitor = utils.monitor.Monitor()

with zipfile.ZipFile('data/ahn_geinterpoleerd.asc.zip') as zipped_asc_file:
    with zipped_asc_file.open('ahn_geinterpoleerd.asc') as asc_file:
        header, array = utils.gis.asc2array(
            asc_file,
            header_length=6,
        )
monitor.check('Import zipped asc into numpy array met custom functie:')

random = numpy.random.randn(*array.shape)
monitor.check( 'Create random array of same size:')

arr1 = array * random
monitor.check( 'Multiply:')

arr2 = array - random
monitor.check( 'Subtract:')
