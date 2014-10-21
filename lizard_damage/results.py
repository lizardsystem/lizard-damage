"""Process results for a DamageEvent.

The idea is that during a calculation a ResultCollector object is kept
around, and generated results (like land use images for a given tile) can
be "thrown to" it."""

import os
import subprocess
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

        # Create an empty zipfile, throw away the old one if needed.
        self.zipfile = mk(self.workdir, ZIP_FILENAME)
        if os.path.exists(self.zipfile):
            os.remove(self.zipfile)

        self.mins = {'depth': float("+inf"), 'height': float("+inf")}
        self.maxes = {'depth': float("-inf"), 'height': float("-inf")}

    def png_path(self, result_type, tile):
        return mk(self.workdir, result_type, "{}.png".format(tile))

    def save_ma(self, tile, masked_array, result_type, ds_template=None):
        self.save_ma_to_geoimage(tile, masked_array, result_type)

        if result_type == 'damage':
            self.save_ma_to_zipfile(
                tile, masked_array, result_type, ds_template)

    def save_ma_to_zipfile(self, tile, masked_array, result_type, ds_template):
        from lizard_damage import calc
        tempfile = calc.mkstemp_and_close()
        calc.write_result(
            name=tempfile,
            ma_result=masked_array,
            ds_template=ds_template)
        self.save_file_for_zipfile(
            tempfile, 'schade_{}.asc'.format(tile), delete_after=True)

    def save_ma_to_geoimage(
            self, tile, masked_array, result_type, color_dict=None):
        from lizard_damage import calc

        filename = self.png_path(result_type, tile)

        if result_type == 'damage':
            calc.write_image(filename, masked_array)
        if result_type == 'landuse':
            legend = calc.landuse_legend()
            colormap = mpl.colors.ListedColormap(legend, 'indexed')
            rgba = colormap(masked_array, bytes=True)
            Image.fromarray(rgba).save(filename, 'PNG')
        if result_type in ('depth', 'height'):
            # Before we can do this, we need to know the max and min value,
            # for coloring. So record that, and save the array to a tmp
            # dir. We then make the images in finalize().
            self.mins[result_type] = min(
                self.mins[result_type], np.amin(masked_array))
            self.maxes[result_type] = max(
                self.maxes[result_type], np.amin(masked_array))

            masked_array.dump(
                os.path.join(self.tempdir, "{}.{}".format(tile, result_type)))
            return

        write_extent_pgw(filename.replace('.png', '.pgw'),
                         self.all_leaves[tile])

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

    def draw_roads(self, roads):
        from lizard_damage import calc
        for tile, extent in self.all_leaves.items():
            png_path = self.png_path('damage', tile)
            if os.path.exists(png_path):
                calc.add_roads_to_image(
                    roads=roads, image_path=png_path, extent=extent)

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
                yield result_type, relative, extent


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
