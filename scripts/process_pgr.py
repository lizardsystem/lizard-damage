import utils
import numpy


monitor = utils.monitor.Monitor()

# Note the mode: 1 or 2 
connection_string_external = "PG:host=192.168.1.110 port=5432 dbname='postgisraster' user='postgres' password='Kikker!23' schema='public' table='i14ez2_19' mode=2"


connection_string_local = "PG:host=127.0.0.1 port=5432 dbname='damage' user='buildout' password='buildout' schema='public' table='raster_tmp' mode=2"

ahn_numpy = utils.gis.pgr2array(connection_string_local)
monitor.stop().show('Import postgis raster set with gdal:').clear().start()

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
