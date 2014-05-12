# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django import forms
import gdal
import logging
import tempfile
import os

from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode

from .models import extent_from_dataset
from .raster import extent_within_extent
from .raster import get_area_with_data
from .models import gdal_open
from .models import DamageScenario
from . import landuse_translator

from lizard_damage.conf import settings

logger = logging.getLogger(__name__)


GDAL_TIFF_DRIVER = gdal.GetDriverByName(b'gtiff')

SCENARIO_TYPES = DamageScenario.SCENARIO_TYPES
SCENARIO_TYPES_DICT = DamageScenario.SCENARIO_TYPES_DICT


class CustomRadioSelectRenderer(forms.RadioSelect.renderer):
    """ Modifies some of the Radio buttons to be disabled in HTML,
    based on an externally-appended Actives list. """
    def render(self):
        if not hasattr(self, "actives"):  # oops, forgot to add an Actives list
            return self.original_render()
        return self.my_render()

    def original_render(self):
        return mark_safe(u'<ul>\n%s\n</ul>' % u'\n'.join([u'<li>%s</li>'
            % force_unicode(w) for w in self]))

    def my_render(self):
        """My render function

        Kinda dirty, but it works in our case.
        """
        midList = []
        for x, wid in enumerate(self):
            #print(wid)
            if self.actives[x] == False:
                wid.attrs['disabled'] = True
            if self.help_texts[x]:
                help_text = (
                    '<div class="help_tooltip ss_sprite ss_help" '
                    'title="%s">&nbsp;</div>' % self.help_texts[x])
            else:
                help_text = '<div class="help_tooltip">&nbsp;</div>'
            midList.append(
                u'<div class="wizard-item-row">%s%s</div>'
                % (help_text, force_unicode(wid)))
        finalList = mark_safe(
            u'<div class="span9 wizard-radio-select">%s</div>'
            % u'\n'.join(midList))
        return finalList


class FormStep0(forms.Form):
    """
    Name and e-mail
    """
    display_title = 'WaterSchadeSchatter'

    name = forms.CharField(
        max_length=100,
        label='Hoe wilt u het scenario noemen?',
        help_text='Deze naam wordt gebruikt voor het uitvoerbestand. '
        'Indien u niets opgeeft wordt de naam van het waterstand-invoerbestand'
        ' gebruikt en voorzien van de suffix ‘resultaat’.'
    )
    email = forms.EmailField(
        label='Emailadres',
    )

    scenario_type = forms.ChoiceField(
        label='Kies het type gegevens waarmee u '
              'een schadeberekening wilt uitvoeren',
        choices=SCENARIO_TYPES,
        widget=forms.widgets.RadioSelect(renderer=CustomRadioSelectRenderer),
    )
    scenario_type.widget.renderer.actives = [
        True, True, True, True, True, False, True]
    scenario_type.widget.renderer.help_texts = [
        'Kies deze optie indien u één kaart heeft met de waterstand in meter '
        't.o.v. NAP die hoort bij één water- overlastgebeurtenis. Het gewenste'
        ' formaat is ASCI met RD als coordinatenstelsel.',
        'Kies deze optie indien u één kaart heeft met de waterstand in meter '
        't.o.v. NAP die hoort bij één herhalingstijd. Het gewenste formaat is '
        'ASCI met RD als coordinaten-stelsel.',
        'Kies deze optie indien u voor alle tijdstappen van een '
        'wateroverlast-gebeurtenis kaarten heeft met de waterstand in meter '
        't.o.v. NAP. Het gewenste formaat is ASCI met RD als '
        'coordinatenstelsel.',
        'Kies deze optie indien u voor meerdere gebeurtenissen kaarten heeft '
        'met de maximale waterstand in meter t.o.v. NAP. Het gewenste formaat '
        'is ASCI met RD als coordinatenstelsel.',
        'Kies deze optie indien u voor meerdere herhalingstijden kaarten '
        'heeft met de waterstand in meter t.o.v. NAP. Het gewenste formaat'
        ' is ASCI met RD als coordinatenstelsel. Bij deze methode wordt '
        'tevens automatisch een risicokaart gemaakt. Deze risicokaart is nodig'
        ' voor het berekenen van baten van maatregelen.',
        'Kies deze optie indien u voor een tijdserie kaarten heeft met per '
        'tijdstap de waterstand in meter t.o.v. NAP. Het gewenste formaat is'
        ' ASCI met RD als coordinatenstelsel.',
        'Kies deze optie indien u een batenkaart wilt maken op basis van'
        ' risicokaarten.']


class FormStep1(forms.Form):
    """
    Scenario info (based on 1 kaart, 1 gebeurtenis)
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[0]

    MONTH_CHOICES = (
        (1, 'januari'),
        (2, 'februari'),
        (3, 'maart'),
        (4, 'april'),
        (5, 'mei'),
        (6, 'juni'),
        (7, 'juli'),
        (8, 'augustus'),
        (9, 'september'),
        (10, 'oktober'),
        (11, 'november'),
        (12, 'december'),
        )

    waterlevel = forms.FileField(
        label="Ascii bestand maximale waterstand",
        required=True,
        help_text='Dit is het bestand met waterstanden in mNAP voor het '
        'gebied waarvoor u de berekening wilt uitvoeren.')

    damagetable = forms.FileField(
        label="Optioneel: eigen schadetabel", required=False,
        help_text='Het is mogelijk om eigen schadebedragen te gebruiken. '
        'Download hiervoor de standaard schade tabel en verander deze naar '
        'behoefte.'
        )

    customheights = forms.FileField(
        label="Optioneel: eigen hoogtekaart", required=False,
        help_text='Het is mogelijk om een eigen hoogtekaart te gebruiken. '
        'Upload hiervoor een dataset (ASCII of GeoTIFF) die minstens het '
        'gebied van het maximale waterstandsbestand beslaat. '
        )

    customlanduse = forms.FileField(
        label="Optioneel: eigen landgebruikskaart", required=False,
        help_text='Het is mogelijk om een eigen landgebruikskaart te '
        'gebruiken. Upload hiervoor een dataset (ASCII of GeoTIFF) '
        'die minstens het gebied van het maximale waterstandsbestand beslaat. '
        )

    customlanduseexcel = forms.FileField(
        label="Optioneel: vertaaltabel bij eigen landgebruikskaart",
        required=False,
        help_text='Als u een eigen landgebruikskaart gebruikt, kan het zijn '
        'dat uw kaart andere codes gebruikt voor de verschillende typen '
        'landgebruik. In dit geval kan er een Excel file meegeleverd worden '
        'die gebruikt zal worden om de codes om te nummeren. Zie het '
        'voorbeeldbestand.')

    floodtime = forms.FloatField(
        label="Duur overlast (uur)",
        help_text="Hiermee wordt de periode bedoeld waarbij er daadwerkelijk"
        " water op straat, in huizen of op de akkers staat. Afhankelijk van"
        " het landgebruik en deze duur wordt meer of minder schade berekend.")

    repairtime_roads = forms.ChoiceField(
        label="Hersteltijd wegen", required=True,
        choices=(
            ("0.0", "0 uur"), ("0.25", "6 uur"), ("1", "1 dag"),
            ("2", "2 dagen"), ("5", "5 dagen"), ("10", "10 dagen")),
        help_text='Met hersteltijd wegen wordt de duur bedoeld dat wegen niet '
        'gebruikt kunnen worden. Voor deze duur wordt indirecte schade '
        'berekend als gevolg van de extra kosten die mensen maken voor het '
        'omrijden. Deze schade wordt enkel berekend voor primaire wegen '
        '(snelwegen e.d.) en secundaire wegen (regionale en lokale wegen) '
        'indien minimaal 100 m2 van een wegvak was geïnundeerd. De duur is '
        'gelijk aan de duur van de wateroverlast plus de tijd die nodig is om '
        'de schade herstellen. Nadat het water van de weg af is, kan een weg '
        'namelijk niet altijd meteen gebruikt worden doordat eerst slib en '
        'vuil verwijderd moet worden of de weg nog geblokkeerd is door '
        'bijvoorbeeld achtergebleven auto’s, de leidingen van noodpompen e.d.'
        )

    repairtime_buildings = forms.ChoiceField(
        label="Hersteltijd bebouwing", required=True,
        choices=(
            ("0.0", "0 uur"), ("0.25", "6 uur"), ("1", "1 dag"),
            ("2", "2 dagen"), ("5", "5 dagen"), ("10", "10 dagen")),
        help_text='Met hersteltijd bebouwing wordt de duur bedoeld dat een '
        'gebouw zijn oorspronkelijke functie niet kan vervullen. Dit is '
        'gelijk aan de duur van de wateroverlast en de tijd om de schade '
        'te herstellen. Gedurende deze periode loopt een winkel bijvoorbeeld'
        ' zijn omzet mis of moet een familie ondergebracht worden in een'
        ' hotel.'
        )

    floodmonth = forms.ChoiceField(
        label="Wat is de maand van de gebeurtenis?",
        choices=MONTH_CHOICES, initial=9,
        help_text='Voor de landgebruikscategorien als hooigras en landbouw '
        'is de schade afhankelijk van het tijdstip in het groeiseizoen. In '
        'de winter is er minder schade dan in de zomer. Indien u niets invult'
        ' wordt default uitgegaan van september.')

    calc_type = forms.ChoiceField(
        label="Gemiddelde, minimale of maximale schadebedragen "
        "en schadefuncties",
        choices=DamageScenario.CALC_TYPE_CHOICES,
        initial=DamageScenario.CALC_TYPE_AVG,
        help_text='Voer uw schadeberekening uit met voor Nederland '
        'gemiddelde, maximale of minimale schadebedragen en schadefuncties.')

    def add_field_error(self, field, message):
        """Assumes this field has no errors yet"""
        self._errors[field] = self.error_class([message])

    @property
    def temp_directory(self):
        if not hasattr(self, '_temp_directory'):
            self._temp_directory = tempfile.mkdtemp()
        return self._temp_directory

    def save_uploaded_gdal_file_field(self, fieldname):
        uploadedfile = self.cleaned_data.get(fieldname)
        if uploadedfile is None:
            return

        filename = os.path.join(self.temp_directory, uploadedfile.name)
        with open(filename, 'wb') as f:
            for chunk in uploadedfile.chunks():
                f.write(chunk)

        dataset = gdal_open(filename)
        if dataset is None:
            self.add_field_error(fieldname, "Kan raster niet openen.")
            dataset = None
            os.remove(filename)
        else:
            self.cleaned_data[fieldname + '_file'] = filename
            self.cleaned_data[fieldname + '_dataset'] = dataset

    def save_uploaded_excel_file(self, fieldname):
        uploadedfile = self.cleaned_data.get(fieldname)
        if uploadedfile is None:
            return

        filename = os.path.join(self.temp_directory, uploadedfile.name)
        with open(filename, 'wb') as f:
            for chunk in uploadedfile.chunks():
                f.write(chunk)

        try:
            translator = landuse_translator.LanduseTranslator(filename)
            translator.check()
        except landuse_translator.TranslatorException as e:
            self.add_field_error(fieldname, e.description)
            os.remove(filename)
            return

        self.cleaned_data[fieldname + "_file"] = filename
        self.cleaned_data[fieldname + "_translator"] = translator

    def clean_customlanduse(self):
        self.save_uploaded_gdal_file_field('customlanduse')
        return self.cleaned_data.get('customlanduse')

    def clean_customlanduseexcel(self):
        if (self.cleaned_data['customlanduseexcel'] and not
            self.cleaned_data['customlanduse']):
            self.add_field_error(
                'customlanduseexcel',
                "Uploaden van een vertaaltabelbestand heeft "
                "alleen zin als er een eigen landgebruikskaart "
                "gebruikt wordt.")

        self.save_uploaded_excel_file('customlanduseexcel')

        return self.cleaned_data['customlanduseexcel']

    def clean_customheights(self):
        self.save_uploaded_gdal_file_field('customheights')
        return self.cleaned_data.get('customheights')

    def clean_waterlevel(self):
        self.save_uploaded_gdal_file_field('waterlevel')

        ds = self.cleaned_data.get('waterlevel_dataset')
        if ds:
            if (get_area_with_data(ds) >
                settings.LIZARD_DAMAGE_MAX_WATERLEVEL_SIZE):
                self.add_field_error(
                    'waterlevel',
                    'Het waterstand bestand mag maximaal 200km2 beslaan.')

        return self.cleaned_data.get('waterlevel')

    def clean(self):
        """Checks that apply to more than one field."""
        cleaned_data = super(FormStep1, self).clean()

        # Check the landuse Excel sheet
        translator = self.cleaned_data.get('customlanduseexcel_translator')
        landuse = self.cleaned_data.get('customlanduse_dataset')
        if translator and landuse:
            try:
                translator.check_with_dataset(landuse)

                # It's apparently correct. Use it to translate the
                # customlanduse dataset, creating a new one. It's a
                # bit dirty to do this in the form, but OK...
                dataset = self.cleaned_data.get('customlanduse_dataset')
                grid = dataset.GetRasterBand(1).ReadAsArray()

                new_filename = str(os.path.join(
                    self.temp_directory, 'translated_landusemap.tiff'))
                new_dataset = GDAL_TIFF_DRIVER.CreateCopy(
                    new_filename, dataset)
                band = new_dataset.GetRasterBand(1)
                band.WriteArray(translator.translate_grid(grid))
                band.SetNoDataValue(translator.NODATA_VALUE)
                del new_dataset
                del dataset
                os.remove(self.cleaned_data.get('customlanduse_file'))
                self.cleaned_data['customlanduse_file'] = new_filename
            except landuse_translator.TranslatorException as e:
                self.add_field_error(
                    'customlanduseexcel', e.description)

        # This closes the datasets, we don't need them anymore at
        # this stage
        for key in ('customlanduse_dataset', 'customheights_dataset',
                    'waterlevel_dataset'):
            if key in cleaned_data:
                del cleaned_data[key]

        cleaned_data['temporary_directory'] = self.temp_directory

        return cleaned_data


class FormStep2(FormStep1):
    """
    Scenario_type 1
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[1]
    repetition_time = forms.FloatField(
        label="Herhalingstijd (jaar)", help_text="")


class FormStep3(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[2]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep4(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[3]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep5(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[4]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep6(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[5]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep7(forms.Form):
    """
    """
    display_title = 'Controle invoer'

    test_title = forms.CharField(max_length=100)


class FormZipResult(forms.Form):
    """
    """
    display_title = 'Controle invoer'

    zip_content = forms.CharField(
        max_length=100,
        label="zipfile analyse",
        widget=forms.Textarea(attrs={'readonly': 'readonly'}))

    # def __init__(self, *args, **kwargs):
    #     super(FormZipResult, self).__init__(*args, **kwargs)
    #     instance = getattr(self, 'instance', None)
    #     if instance and instance.id:
    #         self.fields['zip_content'].widget.attrs['readonly'] = True

    #test = forms.CharField(max_length=100, label="")
    # test2 = forms.CharField(max_length=100, label="")


    # def __init__(self, *args, **kwargs):
    #     extra = kwargs.pop('extra')
    #     super(FormZipResult, self).__init__(*args, **kwargs)

    #     for i, question in extra:
    #         self.fields['custom_%s' % i] = forms.CharField(label=question)


class FormBatenKaart(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[6]
    display_description = (
        'Voer risicokaarten in om een batenkaart te maken. Deze kaarten'
        ' zijn te downloaden van resultaatpagina\'s.')

    zipfile_risk_before = forms.FileField(
        label="Zipbestand risico voor", required=True)
    zipfile_risk_after = forms.FileField(
        label="Zipbestand risico na", required=True)
