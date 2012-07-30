import numpy
import utils
import gc

monitor = utils.monitor.Monitor()
ahn_numpy = numpy.genfromtxt('data/ahn_geinterpoleerd.asc', skip_header=6)
monitor.stop().show('Import asc into numpy array met generieke functie:').clear().start()

gc.collect()
monitor.stop().show('Cleanup via garbage collect:').clear().start()

random = numpy.random.randn(*ahn_numpy.shape)
monitor.stop().show( 'Create random array of same size:').clear().start()

arr1 = ahn_numpy * random
monitor.stop().show( 'Multiply:').clear().start()

arr2 = ahn_numpy - random
monitor.stop().show( 'Subtract:').clear().start()
