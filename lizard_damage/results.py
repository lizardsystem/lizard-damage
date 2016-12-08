"""Process results for a DamageEvent.

The idea is that during a calculation a ResultCollector object is kept
around, and generated results (like land use images for a given tile) can
be "thrown to" it."""

import glob
import os
import subprocess
import tempfile
import zipfile

from PIL import Image
from pyproj import Proj
import matplotlib as mpl
import numpy as np

ZIP_FILENAME = 'result.zip'

RD = str(
    "+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.999908"
    " +x_0=155000 +y_0=463000 +ellps=bessel +units=m +towgs84=565.2369,"
    "50.0087,465.658,-0.406857330322398,0.350732676542563,-1.8703473836068,"
    "4.0812 +no_defs <>"
)

WGS84 = str('+proj=latlong +datum=WGS84')

rd_proj = Proj(RD)
wgs84_proj = Proj(WGS84)

CDICT_HEIGHT = {
    'red': ((0.0, 51. / 256, 51. / 256),
            (0.5, 237. / 256, 237. / 256),
            (1.0, 83. / 256, 83. / 256)),
    'green': ((0.0, 114. / 256, 114. / 256),
              (0.5, 245. / 256, 245. / 256),
              (1.0, 83. / 256, 83. / 256)),
    'blue': ((0.0, 54. / 256, 54. / 256),
             (0.5, 170. / 256, 170. / 256),
             (1.0, 83. / 256, 83. / 256)),
}

CDICT_WATER_DEPTH = {
    'red': ((0.0, 170. / 256, 170. / 256),
            (0.5, 65. / 256, 65. / 256),
            (1.0, 4. / 256, 4. / 256)),
    'green': ((0.0, 200. / 256, 200. / 256),
              (0.5, 120. / 256, 120. / 256),
              (1.0, 65. / 256, 65. / 256)),
    'blue': ((0.0, 255. / 256, 255. / 256),
             (0.5, 221. / 256, 221. / 256),
             (1.0, 176. / 256, 176. / 256)),
    }


class ResultCollector(object):
    def __init__(self, workdir, all_leaves, logger):
        """Start a new ResultCollector.

        Workdir is a damage event's workdir. All result files are placed
        in that directory, or subdirectories of it.

        all_leaves is an iterable of (ahn_name, extent) tuples that
        is mainly used to know what the entire extent is going to be
        in advance.

        All files are placed in the damage event's directory.

        Results that are tracked:
        - Files to be added to a result zipfile

        - Landuse tiles
        - Water depth tiles
        - Height tiles
        - Damage tiles.

        The damage tiles are added as ASC's to the result zipfile.

        All four types of tile are saved as images for showing using Google.
        The damage tiles are somewhat special in that they will first be
        saved, and need to have roads drawn in them afterwards.
        """

        self.workdir = workdir

        self.tempdir = os.path.join(self.workdir, 'tmp')
        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)

        self.logger = logger

        # We want to know all leaves in advance, so we can make images for
        # the entire region, or sections of it, without having to let them
        # correspond 1:1 to the tiles.
        self.all_leaves = {
            ahn_name: extent for (ahn_name, extent) in all_leaves
        }
        self.riskmap_data = []

        # Create an empty zipfile, throw away the old one if needed.
        self.zipfile = mk(self.workdir, ZIP_FILENAME)
        if os.path.exists(self.zipfile):
            os.remove(self.zipfile)

        self.mins = {'depth': float("+inf"), 'height': float("+inf")}
        self.maxes = {'depth': float("-inf"), 'height': float("-inf")}

    def png_path(self, result_type, tile):
        return mk(self.workdir, result_type, "{}.png".format(tile))

    def save_ma(
            self, tile, masked_array, result_type, ds_template=None,
            repetition_time=None):
        # self.save_ma_to_geoimage(tile, masked_array, result_type)
        # ^^^ disable because google maps api no longer supports this,
        #     and because tmp takes excessive space because of this
        #     (uncompressed) storage.
        if result_type == 'damage':
            filename = self.save_ma_to_asc(
                tile, masked_array, result_type, ds_template, repetition_time)
            if repetition_time is not None:
                # TODO (Reinout wants to know where this is used. The file is
                # deleted after adding it to the zipfile, so....)
                self.riskmap_data.append(
                    (tile, repetition_time, filename))

    def save_ma_to_asc(
            self, tile, masked_array, result_type, ds_template,
            repetition_time):
        from lizard_damage import calc
        if repetition_time is not None:
            filename = 'schade_{}_T{}.asc'.format(tile, repetition_time)
        else:
            filename = 'schade_{}.asc'.format(tile)
        filename = os.path.join(self.tempdir, filename)
        calc.write_result(
            name=filename,
            ma_result=masked_array,
            ds_template=ds_template)

        return filename

    def save_csv_data_for_zipfile(self, zipname, csvdata):
        from lizard_damage import calc
        filename = calc.mkstemp_and_close()
        calc.write_table(name=filename, **csvdata)
        self.save_file_for_zipfile(filename, zipname, delete_after=True)

    def save_file_for_zipfile(self, file_path, zipname, delete_after=False):
        with zipfile.ZipFile(self.zipfile, 'a', zipfile.ZIP_DEFLATED) as myzip:
            self.logger.info('zipping %s...' % zipname)
            myzip.write(file_path, zipname)
            if delete_after:
                self.logger.info(
                    'removing %r (%s in arc)' % (file_path, zipname))
                os.remove(file_path)

    def build_damage_geotiff(self):
        # for i in *asc; do gdal_translate $i ${i/asc/tif} -co compress=deflate -co tiled=yes -ot float32; done
        # gdalbuildvrt all.vrt *tif
        orig_dir = os.getcwd()
        os.chdir(self.tempdir)
        asc_files = glob.glob('*.asc')
        if not asc_files:
            self.logger.info("No asc files as input, not writing out a geotiff.")
        for asc_file in asc_files:
            tiff_file = asc_file.replace('.asc', '.tiff')
            cmd = ("gdal_translate %s %s "
                   "-co compress=deflate -co tiled=yes -ot float32")
            os.system(cmd % (asc_file, tiff_file))
            self.save_file_for_zipfile(tiff_file, tiff_file)

        file_with_tiff_filenames = tempfile.NamedTemporaryFile()
        tiff_files = glob.glob('*.tiff')
        for tiff_file in tiff_files:
            file_with_tiff_filenames.write(tiff_file + "\n")
        file_with_tiff_filenames.flush()
        vrt_file = 'schade.vrt'
        cmd = "gdalbuildvrt -input_file_list %s %s" % (
            file_with_tiff_filenames.name, vrt_file)
        self.logger.debug(cmd)
        os.system(cmd )
        file_with_tiff_filenames.close() # Deletes the temporary file
        self.save_file_for_zipfile(vrt_file, vrt_file)
        os.chdir(orig_dir)

    def finalize(self):
        """Make final version of the data:

        - Warp all generated geoimages to WGS84.
        """

        self.extents = {}

        for tile in self.all_leaves:
            for result_type in ('height', 'depth'):
                tmp_filename = os.path.join(
                    self.tempdir, "{}.{}".format(tile, result_type))
                if os.path.exists(tmp_filename):
                    masked_array = np.load(tmp_filename)
                    os.remove(tmp_filename)

                    normalize = mpl.colors.Normalize(
                        vmin=self.mins[result_type],
                        vmax=self.maxes[result_type])
                    if result_type == 'height':
                        cdict = CDICT_HEIGHT
                    elif result_type == 'depth':
                        cdict = CDICT_WATER_DEPTH
                    colormap = mpl.colors.LinearSegmentedColormap(
                        'something', cdict, N=1024)
                    rgba = colormap(normalize(masked_array), bytes=True)
                    if result_type == 'depth':
                        rgba[:, :, 3] = np.where(
                            np.greater(masked_array.filled(0), 0), 255, 0)
                    filename = self.png_path(result_type, tile)
                    Image.fromarray(rgba).save(filename, 'PNG')
                    write_extent_pgw(filename.replace('.png', '.pgw'),
                                     self.all_leaves[tile])

            for result_type in ('damage', 'landuse', 'height', 'depth'):
                png = self.png_path(result_type, tile)
                if os.path.exists(png):
                    result_extent = rd_to_wgs84(png)
                    self.extents[(tile, result_type)] = result_extent

    def all_images(self):
        """Generate path and extent of all created images. Path is relative
        to the workdir. Only use after finalizing."""
        for ((tile, result_type), extent) in self.extents.items():
            png_path = self.png_path(result_type, tile)
            if os.path.exists(png_path):
                relative = png_path[len(self.workdir):]
                yield (result_type, relative, extent)


def write_extent_pgw(name, extent):
    """write pgw file:

    0.5
    0.000
    0.000
    0.5
    <x ul corner>
    <y ul corner>

    extent is a 4-tuple
    """
    f = open(name, 'w')
    f.write('0.5\n0.000\n0.000\n-0.5\n')
    f.write('%f\n%f' % (min(extent[0], extent[2]), max(extent[1], extent[3])))
    f.close()


def mk(*parts):
    """Combine parts using os.path.join, then make sure the directory
    exists."""
    path = os.path.join(*parts)
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    return path


def rd_to_wgs84(png):
    from lizard_damage import models

    # Step 1: warp using gdalwarp to lon/lat in .tif
    # Warp png file, output is tif.
    tif = png.replace('.png', '.tif')
    subprocess.call([
        'gdalwarp', png, tif,
        '-t_srs', "+proj=latlong +datum=WGS84", '-s_srs', RD.strip()])

    # Step 2: convert .tif back to .png
    im = Image.open(tif)
    im.save(png, 'PNG')

    # Step 3: We can't save this WGS84 as a PGW (or at least, we don't).
    # Remove the old PGW and return this extent.
    result_extent = models.extent_from_geotiff(tif)
    os.remove(png.replace('.png', '.pgw'))

    # Step 4: remove TIF
    os.remove(tif)

    return result_extent
