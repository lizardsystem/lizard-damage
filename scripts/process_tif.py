import Image
import numpy
import utils

monitor = utils.monitor.Monitor()
ahn_pil = Image.open('data/ahn.tif')
ahn_numpy = numpy.array(ahn_pil.getdata()).reshape(*reversed(ahn_pil.size))
monitor.stop().show('Import tif and create numpy array:').clear().start()
del ahn_pil
monitor.stop().show( 'Cleanup memory:').clear().start()

random = numpy.random.randn(*ahn_numpy.shape)
monitor.stop().show( 'Create random array of same size:').clear().start()

arr1 = ahn_numpy * random
monitor.stop().show( 'Multiply:').clear().start()

arr2 = ahn_numpy - random
monitor.stop().show( 'Subtract:').clear().start()
