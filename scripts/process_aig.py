import utils
import numpy


monitor = utils.monitor.Monitor()

ahn_numpy = utils.gis.aig2array('data/i37en1_05')
monitor.stop().show('Import aig file set with gdal:').clear().start()

random = numpy.random.randn(*ahn_numpy.shape)
monitor.stop().show( 'Create random array of same size:').clear().start()

arr1 = ahn_numpy * random
monitor.stop().show( 'Multiply:').clear().start()

arr2 = ahn_numpy - random
monitor.stop().show( 'Subtract:').clear().start()

perc90 = numpy.percentile(ahn_numpy, 90)
monitor.stop().show( '90 Percentile:').clear().start()

with open('data/ahn_geinterpoleerd.asc') as ascfile:
    dumpstr = ascfile.read()
monitor.stop().show( 'Read asc in mem:').clear().start()
