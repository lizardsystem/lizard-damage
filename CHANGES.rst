Changelog of lizard-damage
===================================================


3.1.4 (unreleased)
------------------

- Nothing changed yet.


3.1.3 (2018-03-23)
------------------

- Added a link to stowa.lizard.net, which shows the default maps.


3.1.2 (2018-03-12)
------------------

- Added release notes document.


3.1.1 (2018-03-12)
------------------

- Global buildout.

- Fixed missing chdir trouble when no VRT is created.


3.1 (2017-12-22)
----------------

- Added support for AHN3


3.0.0 (2017-07-03)
------------------

- Increased major version number.


2.5.2 (2017-06-09)
------------------

- Updated documentation.


2.5.1 (2017-06-08)
------------------

- Moved default damage table from here to parent repo.


2.5 (2017-06-02)
----------------

- Removed the damagetable from here, it is not used by the calculation.

- Adjusted the road gridcodes to the new landuse map.

- Fixed selection screen errors.


2.4 (2017-05-05)
----------------

- Added batch calculation of uniform levels. Including email at the start of
  calculation as it can take a long time.


2.3 (2016-12-15)
----------------

- Removing temp dir as last step to get rid of bulky ascii files.


2.2 (2016-12-12)
----------------

- Added projection assignment to tiff generation.


2.1 (2016-12-12)
----------------

- Added docker setup for local development, including a ``Jenkinsfile`` for
  automatic testing on jenkins.

- Updated lizard-map version to a 4.x version that includes a fix for the
  jsonfield-problem with an old lizard-map migration.

- After generating tiles, a matching VRT is also created.


2.0.6 (2016-08-31)
------------------

- Nothing changed yet.


2.0.5 (2015-11-24)
------------------

- Fix custom landuse bug.


2.0.4 (2015-06-30)
------------------

- Update manuals after update of height tiles in the east.


2.0.3 (2015-06-24)
------------------

- Disable the image generation, since tmp takes a lot of space and google
  does not support at any way.


2.0.2 (2015-03-26)
------------------

- Update cleanup command.

- Fix names of tasks to be picked up by cleanup command.


2.0.1 (2015-03-26)
------------------

- Fix calculation type parsing.


2.0.0 (2015-03-26)
------------------

- Make risk maps work with refactored result collector.


1.2.2 (2015-03-17)
------------------

- Test for include package data and templates


1.2.1 (2015-03-17)
------------------

- Rewrite zipfile analysis and unpacking

- Disable area check

- Disable google maps view in result page


1.2 (2014-11-04)
----------------

- Swapped potatoes.


1.1 (2014-08-05)
----------------

- Make lizard-damage compatible with Django 1.6.5.


1.0.1 (2014-07-31)
------------------

- Update version string to "mei 2014".


1.0 (2014-07-15)
----------------

- Remove the obsolete AhnIndex model.

- Save custom landuse map in a GeoImage, use only the scenario's
  landuse map slug for the landuse KML if a custom map was uploaded
  (so not tiled in that case).

- Send email if an exception occurs in a task (one to the user,
  one with a traceback to the servicedesk).

- Max size of a scenario is now set at 200km2.

- With custom height and landuse maps, we don't require them to cover
  the entire waterlevel area anymore, using the default maps to fill
  in the rest (in fact, we always use the default maps, and project
  the custom maps over them). This is more useful for users, and
  actually less code.


0.10.2 (2014-02-26)
-------------------

- Bugfix


0.10.1 (2014-02-26)
-------------------

- Bugfix


0.10 (2014-02-26)
-----------------

- Do not use the postgis raster database and the django cache anymore

- Instead use a directory as source for landuse and dem data

- Determine the part with data in waterlevel files and skip other tiles


0.9.35 (2013-11-11)
-------------------

- Update damagetable, 27 and 49 must be the same.


0.9.34 (2013-10-07)
-------------------

- Subtract differently in benefitmap creation.


0.9.33 (2013-09-24)
-------------------

- Fix riskmap calculation: Risk is no longer discarded after mask changes shape.


0.9.32 (2013-03-21)
-------------------

- Added stats logging for benefit tasks as well.


0.9.31 (2013-03-20)
-------------------

- Added logging for stats.


0.9.30 (2013-03-19)
-------------------

- Adjust asc file fix function to remove anything that does
  not look like a aaigrid header.


0.9.29 (2013-03-11)
-------------------

- Added log for scenario being created -> for stats.


0.9.28 (2013-03-07)
-------------------

- Updated help files.


0.9.27 (2013-02-28)
-------------------

- Updated help files, added e-mail address for support.


0.9.26 (2013-01-23)
-------------------

- Removed defaults from damagetable and cfg reader and writer.


0.9.25 (2012-12-22)
-------------------

- Remove not working links from benefit template
- Add geotransforms to risk and benefit calculations


0.9.24 (2012-12-20)
-------------------

- Use bool check instead of try except when cleaning up benefit results.


0.9.23 (2012-12-18)
-------------------

- Renamed to WaterSchadeSchatter.


0.9.22 (2012-12-12)
-------------------

- Put traceback code back in place.


0.9.21 (2012-12-12)
-------------------

- Updated help files with new name "WaterSchadeSchatter".

- Add missing import traceback, but use logger.exception.


0.9.20 (2012-11-19)
-------------------

- Nothing changed yet.


0.9.19 (2012-11-12)
-------------------

- Make depth transparent if it is zero or less
- Make depth link always visible, even when not logged in.


0.9.18 (2012-11-08)
-------------------

- Fix missing import and circular import.


0.9.17 (2012-11-08)
-------------------

- Add risk calculation and downloadable risk asc file on result page.


0.9.16 (2012-11-01)
-------------------

- Improvement in KML view: now all tiles are necessarily there.


0.9.15 (2012-11-01)
-------------------

- Test why depth maps are not always ucreated.


0.9.14 (2012-11-01)
-------------------

- More try-except.


0.9.13 (2012-10-31)
-------------------

- Put more inside try-except


0.9.12 (2012-10-31)
-------------------

- Fixed something


0.9.11 (2012-10-31)
-------------------

- Nothing changed yet.


0.9.10 (2012-10-31)
-------------------

- Same bugfix again.


0.9.9 (2012-10-31)
------------------

- Bugfix if depth is only mask.


0.9.8 (2012-10-31)
------------------

- Added depth map in result.


0.9.7 (2012-10-29)
------------------

- Fixes indirect damage being calculated regardless of inundation.


0.9.6 (2012-10-24)
------------------

- Nothing changed yet.


0.9.5 (2012-10-23)
------------------

- Add code for tracks to special treatment list.


0.9.4 (2012-10-22)
------------------

- Make indirectly damaged roads darker.


0.9.3 (2012-10-22)
------------------

- Add indirect damage for roads to image.

- Skip processing of landuse codes when they are not present in landuse array.


0.9.2 (2012-10-16)
------------------

- Updated damage table for download.


0.9.1 (2012-10-11)
------------------

- Fixed management command clean up to remove tasks too.


0.9 (2012-10-11)
----------------

- Now deleting temporary upload zip files after adding them to the db.


0.8.12 (2012-10-11)
-------------------

- Hopefully fixed upload error by specifying the django upload temp
  dir statically.


0.8.11 (2012-10-11)
-------------------

- Added logging for eventually fixing upload error.


0.8.10 (2012-10-10)
-------------------

- Updated logging for views.

- Added reference to scenario id in thank you screen.


0.8.9 (2012-10-10)
------------------

- Add equals to limit for indirect road damage.


0.8.8 (2012-10-10)
------------------

- Do not crash when multiple GeoImage objects have the same slug.


0.8.7 (2012-10-10)
------------------

- Fixed clean_up script.

- Fix factor 3600*24 in indirect damage calculation.


0.8.6 (2012-10-10)
------------------

- Landuse images now have the whole tile extent.


0.8.5 (2012-10-10)
------------------

- Changed height legend (which is dynamically created) so it looks
  like a static file.


0.8.4 (2012-10-10)
------------------

- Experiment with height legend.


0.8.3 (2012-10-10)
------------------

- Fixed damage table.


0.8.2 (2012-10-10)
------------------

- Added option "0 uur" for hersteltijd wegen, added defaults.

- Updated (default) damage table.

- Damage table: Changed standaard_inundatieperiode to
  standaard_inundatieduur.

- Changed kml legend visibility to 1.

- Change threshold for indirect road damage.


0.8.1 (2012-10-10)
------------------

- Added dependency on Pillow, updated imports.


0.8 (2012-10-09)
----------------

- Help texts now on the left.

- Small help improvements.

- Added 6 hour to hersteltijd wegen.

- Bugfix hersteltijd bebouwing.

- Added legends for land use and height.


0.7.4 (2012-10-09)
------------------

- Changed colors of landuse.


0.7.3 (2012-10-08)
------------------

- Bugfix.


0.7.2 (2012-10-08)
------------------

- Changed naming of tasks: prevent deleting wrong scenarios and
  sorting is now better.


0.7.1 (2012-10-08)
------------------

- Changed mktemp to use mkstemp. This prevents a racecondition bug
  which is possibly the source of a vague tempfile deleting thing on
  the task server.


0.7 (2012-10-08)
----------------

- Added initial landuse and height maps.

- Improved table layout.

- Added BenefitScenario / BenefitScenarioResult models and migrations.

- Added forms for benefit scenario.


0.6.10 (2012-10-02)
-------------------

- Now sends email to creator and Jack in case of errors.


0.6.9 (2012-10-02)
------------------

- Zip results after each tile -> else the harddisk will be flooded when
  calculating big scenarios.


0.6.8 (2012-10-02)
------------------

- Replace migrations by one initial migration, that excludes the models
  AhnIndex and Roads

- Make AhnIndex refer to raster server via router.


0.6.7 (2012-10-01)
------------------

- Reduced caching time to 1 day, will only cache when there is more than 2 GB
  free.


0.6.6 (2012-09-27)
------------------

- Fix too large indirect damage for the roads.


0.6.5 (2012-09-27)
------------------

- Added extra try/except.


0.6.4 (2012-09-27)
------------------

- Improved logging.


0.6.3 (2012-09-27)
------------------

- Made it more robust.


0.6.2 (2012-09-27)
------------------

- Added .asc correcting code when sobek adds a line.


0.6.1 (2012-09-27)
------------------

- Adjust colors and legend to yellow, red and orange.


0.6 (2012-09-27)
----------------

- Added warping output files (implemented using gdalwarp).


0.5.13 (2012-09-26)
-------------------

- Add units to unit fixture for indirect damage


0.5.12 (2012-09-26)
-------------------

- Update damagetable (missing units)

- base_form template.


0.5.11 (2012-09-26)
-------------------

- Added caching to ahn and landuse.

- Fixed some titles.


0.5.10 (2012-09-26)
-------------------

- Update damagetable (indirect and direct damage were equal)


0.5.9 (2012-09-25)
------------------

- Nothing changed yet.


0.5.8 (2012-09-25)
------------------

- Updated tooltips.


0.5.7 (2012-09-25)
------------------

- Updated kml. It seems that google maps does not project items 100% accurately.


0.5.6 (2012-09-25)
------------------

- Changed unicode of DamageEvent.


0.5.5 (2012-09-24)
------------------

- Add one decimal to ha formatter
- Add total row at the top of the results table


0.5.4 (2012-09-24)
------------------

- Nothing changed yet.


0.5.3 (2012-09-24)
------------------

- Slightly changed version, added version to disclaimer page.


0.5.2 (2012-09-24)
------------------

- Added STOWA logo to disclaimer page.


0.5.1 (2012-09-24)
------------------

- Coloring of result according to classes using colormap.


0.5 (2012-09-24)
----------------

- Fixed IE layout by adding property for .container.

- Added extra help texts.

- Renamed Schademodule to Schade Calculator.

- Standard calculation form defaults to september & gemiddelde
schadebedragen.

- Added disclaimer.

- Changed version visualization.


0.4.3 (2012-09-20)
------------------

- Remove debugging import.


0.4.2 (2012-09-20)
------------------

- Change index creation to be more transparent and to work with older numpy.


0.4.1 (2012-09-20)
------------------

- Nothing changed yet.


0.4 (2012-09-19)
----------------

- Nothing changed yet.


0.3.2 (2012-09-19)
------------------

- Remove tiff removal.


0.3.1 (2012-09-19)
------------------

- Fix bug in calculation of swapped depth and height
- Fix wrong mask being used in calculation


0.3 (2012-09-18)
----------------

- Nothing changed yet.


0.2 (2012-09-17)
----------------

- Nothing changed yet.


0.1 (2012-09-10)
----------------

- Initial project structure created with nensskel 1.27.dev0.
