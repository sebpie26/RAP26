import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

import pypsa


def conceptual_model(n, component_data):

    sdac = component_data["S-DAC"]

    # Busses for energy balance
    n.add("Bus", "electricity")
    n.add("Bus", "heat")
    n.add("Bus", "diesel")
    n.add("Bus", "methanol")
    # Dry biomass is transported to the chp plant
    n.add("Bus", "biomass dry")
    n.add("Bus", "biomass fuel")

    # Busses for CO2 balance. Harbor storage is a temporary. Offshore is permanent.
    n.add("Bus", "co2 atmo", carrier="co2")
    n.add("Bus", "co2 offshore storage", carrier="co2")
    n.add("Bus", "co2 harbor storage", carrier="co2")
    n.add("Bus", "co2 captured dac", carrier="co2")
    n.add("Bus", "co2 captured chp", carrier="co2")

    # Generators represent: diesel supply for road transport, methanol supply for shipping, electricity supply from the grid, biomass supply from the forest
    n.add("Generator", "electricity grid", bus="electricity", p_nom=1000, marginal_cost=50)
    n.add("Generator", "diesel", bus="diesel", p_nom=1000, marginal_cost=50)
    n.add("Generator", "methanol", bus="methanol", p_nom=1000, marginal_cost=50)
    n.add("Generator", "biomass dry", bus="biomass dry", p_set=1000, marginal_cost=50)

    #Non-transport links: DAC and biomass CHP with MEA driven CCS
    n.add("Link", "S-DAC",
          bus0="heat", bus1="electricity", bus2="co2 atmo", bus3="co2 captured dac",
          efficiency= -sdac["electricity_demand"] / sdac["heat_demand"], 
          efficiency2= -1 / sdac["heat_demand"],
          efficiency3= sdac["capture_efficiency"] / sdac["heat_demand"],
          p_nom_extendable=True,
          capital_cost=sdac["capex"] / sdac["heat_demand"],
          marginal_cost=sdac["opex"] / sdac["heat_demand"])

    n.add("Link", "CHP+CCS", 
        bus0="biomass fuel", 
        bus1="heat", 
        bus2="electricity",
        bus3="co2 atmo",
        bus4="co2 captured chp",
        efficiency=1, 
        efficiency2=-1, 
        p_nom_extendable=True)



if __name__ == "__main__":
    component_data_savepath = "C:/Users/Sebastian/Documents/VSC Workspace/RAP26/input_data/component_data.yaml"

    with open(component_data_savepath, "r") as f:
        component_data = yaml.safe_load(f)

    n = pypsa.Network()
    n.set_snapshots(range(168))

    conceptual_model(n, component_data)