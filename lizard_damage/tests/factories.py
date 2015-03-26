import factory

from lizard_damage import models


class DamageScenarioFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.DamageScenario


class DamageEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.DamageEvent

    name = "TestDamageEvent"
    status = models.DamageEvent.EVENT_STATUS_RECEIVED
    scenario = factory.SubFactory(DamageScenarioFactory)
    floodtime = 3600.0  # 1 hour


class DamageEventWaterlevelFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.DamageEventWaterlevel

    event = factory.SubFactory(DamageEventFactory)
