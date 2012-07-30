import numpy
import utils


monitor = utils.monitor.Monitor()

with open('data/ahn_geinterpoleerd.asc') as asc_file:
    header, array = utils.gis.asc2array(
        asc_file=asc_file,
        header_length=6,
    )
monitor.stop().show('Import asc into numpy array met custom functie:').clear().start()

random = numpy.random.randn(*array.shape)
monitor.stop().show( 'Create random array of same size:').clear().start()

arr1 = array * random
monitor.stop().show( 'Multiply:').clear().start()

arr2 = array - random
monitor.stop().show( 'Subtract:').clear().start()
