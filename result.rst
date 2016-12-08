Results page
============

I am currently working out how to change the results shown on the
results page for single event, single map damage scenarios. I'm
documenting my findings here. It is likely that I don't describe
everything.

For every damage event, there are six links at the top of the results
page: "bekijken", "downloaden", "kml", "landgebruik", "hoogte",
"diepte". "bekijken" en "kml" are almost identical, since all
"bekijken" does is show the KML file sent by "kml" using Google Maps.

Bekijken / KML
--------------

The URL for the KML is named "lizard_damage_event_kml", which calls
the lizard_damage.views.DamageEventKML view, and it takes an event
slug. It shows a picture on the map with damage levels, and a legend.

Downloaden
----------

This is a link to the DamageEvent's `result` file. It is stored under
MEDIA_ROOT so can be directly linked to.

The `task.calculate_damage` task loops over all damage events of a
scenario, calls `tasks.call_calc_damage_for_waterlevel` on each of
them. That yields a `result` structure, of which the first element is
the zipfile, which is saved to the media directory by
`tasks.process_result`.

Inside the zip file is the damage table used, a CSV file containing
total damage, and a damage grid and CSV per AHN tile.


Landgebruik
===========

Dit is een link naar Google Maps, waar een KML getoond wordt. De URL
name is "lizard_damage_geo_image_landuse_kml , met als argument de
`landuse_slugs` van het damage event.


