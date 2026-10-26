from .boe import BoeConnector
from .companies_house import CompaniesHouseConnector
from .dmo import DmoConnector
from .ecb import EcbConnector
from .energy import CarbonConnector, FuelConnector
from .geography import GeographyConnector
from .hmrc import HmrcConnector
from .land_registry import LandRegistryConnector
from .nomis import NomisConnector
from .ons import OnsConnector

CONNECTORS = {
    c.source_id: c
    for c in (OnsConnector, BoeConnector, EcbConnector, NomisConnector, LandRegistryConnector, HmrcConnector,
              CarbonConnector, FuelConnector, DmoConnector, GeographyConnector, CompaniesHouseConnector)
}
