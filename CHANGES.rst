Changelog of lizard-damage
===================================================


0.8.5 (unreleased)
------------------

- Nothing changed yet.


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
