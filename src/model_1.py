import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

import pypsa


def conceptual_model(component_data, snapshots=168):

    n = pypsa.Network()
    n.set_snapshots(range(snapshots))

    sdac = component_data["S-DAC"]

    # Busses for energy balance
    n.add("Bus", "electricity")
    n.add("Bus", "heat")
    n.add("Bus", "diesel")
    n.add("Bus", "methanol")
    # Dry biomass is transported to the chp plant
    n.add("Carrier", "biomass")
    n.add("Bus", "biomass dry", carrier="biomass")
    n.add("Bus", "biomass fuel", carrier="biomass")

    # Busses for CO2 balance. Harbor storage is a temporary. Offshore is permanent.
    n.add("Carrier", "co2", co2_emissions=-1)
    n.add("Bus", "co2 atmo", carrier="co2")
    n.add("Bus", "co2 offshore storage", carrier="co2")
    n.add("Bus", "co2 harbor storage", carrier="co2")
    n.add("Bus", "co2 captured dac", carrier="co2")
    n.add("Bus", "co2 captured chp", carrier="co2")

    # Generators represent: diesel supply for road transport, methanol supply for shipping, electricity supply from the grid, biomass supply from the forest
    n.add("Generator", "electricity grid", bus="electricity", p_nom=1000, marginal_cost=10)
    #n.add("Generator", "diesel", bus="diesel", p_nom=1000, marginal_cost=50)
    #n.add("Generator", "methanol", bus="methanol", p_nom=1000, marginal_cost=50)
    #n.add("Generator", "biomass dry", bus="biomass dry", p_set=1000, marginal_cost=5)

    # Stores represent: diesel for road transport, methanol for shipping, electricity for the grid, biomass for the forest
    n.add("Store", "diesel store",
          bus="diesel", e_nom=1000, marginal_cost=50)
    n.add("Store", "methanol store",
          bus="methanol", e_nom=1000, marginal_cost=50) 
    n.add("Store", "electricity store",
          bus="electricity", e_nom=1000, marginal_cost=10)
    n.add("Store", "biomass store",
          bus="biomass dry", e_nom=100, e_initial=1000, marginal_cost=5)


    #Non-transport links: DAC and biomass CHP with MEA driven CCS
    n.add("Link", "S-DAC",
          bus0="heat",
          bus1="electricity",
          bus2="co2 atmo",
          bus3="co2 captured dac",
          efficiency= -1, #-sdac["electricity_demand"] / sdac["heat_demand"], 
          efficiency2= -1, # -1 / sdac["heat_demand"],
          efficiency3= 1, #sdac["capture_efficiency"] / sdac["heat_demand"],
          p_nom_extendable=True,
          capital_cost=100, #sdac["capex"] / sdac["heat_demand"],
          marginal_cost=10) #sdac["opex"] / sdac["heat_demand"])

    n.add("Link", "CHP+CCS", 
        bus0="biomass fuel", 
        bus1="heat",
        bus2="electricity",
        bus3="co2 atmo",
        bus4="co2 captured chp",
        efficiency=0.55, 
        efficiency2=0.3,
        efficiency3=1,
        efficiency4=1,
        p_nom_extendable=True,
        capital_cost=100,
        marginal_cost=10)

    # Storage unit for atmosphere, CO2 harbor storage and CO2 offshore storage
    n.add("Store", "co2 atmo", #Express them as stores
          bus="co2 atmo",
          e_nom=100000)

    n.add("Store", "co2 harbor storage",
          bus="co2 harbor storage",
          e_nom=100)

    n.add("Store", "co2 offshore storage", 
          bus="co2 offshore storage", 
          e_nom=1000)

    # Transport links for biomass
    n.add("Link", "biomass road transport",
          bus0="biomass dry",
          bus1="biomass fuel",
          bus2="diesel",
          bus3="co2 atmo",
          efficiency=1,
          efficiency2=-0.1,
          efficiency3=0.1,
          p_nom_extendable=True,
          capital_cost=100,
          marginal_cost=10)

    n.add("Link", "biomass rail transport", 
          bus0="biomass dry",
          bus1="biomass fuel",
          bus2="electricity",
          efficiency=1,
          efficiency2=-0.01, # Assumed: 1% of the energy content of the biomass amounts to the electrical energy used for transportation.
          p_nom_extendable=True,
          capital_cost=50,
          marginal_cost=5)

    #Transport links for CO2
    for bus in ["dac", "chp"]:
        for storloc in ["harbor", "offshore"]:
            n.add("Link", f"co2 ship transport {bus}",
                          bus0=f"co2 captured {bus}",
                          bus1=f"co2 {storloc} storage",
                          bus2="maritime fuel",
                          bus3="co2 atmo",
                          efficiency=1,
                          efficiency2=-1,
                          efficiency3=1,
                          p_nom_extendable=True,
                          capital_cost=100,
                          marginal_cost=10)

            n.add("Link", f"co2 pipeline transport {bus}",
                          bus0=f"co2 captured {bus}",
                          bus1=f"co2 {storloc} storage",
                          bus2="electricity",
                          efficiency=1,
                          p_nom_extendable=True,
                          capital_cost=50,
                          marginal_cost=5)

        n.add("Link", f"co2 road transport {bus}",
            bus0=f"co2 captured {bus}",
            bus1="co2 harbor storage",
            bus2="diesel",
            bus3="co2 atmo",
            efficiency=1,
            efficiency2=-1,
            efficiency3=1,
            p_nom_extendable=True,
            capital_cost=100,
            marginal_cost=10)

        n.add("Link", f"co2 rail transport {bus}",
            bus0=f"co2 captured {bus}",
            bus1="co2 harbor storage",
            bus2="electricity",
            efficiency=1,
            p_nom_extendable=True,
            capital_cost=50,
            marginal_cost=5)

    return n
        

        

if __name__ == "__main__":
    component_data_savepath = "C:/Users/Sebastian/Documents/VSC Workspace/RAP26/input_data/component_data.yaml"

    with open(component_data_savepath, "r") as f:
        component_data = yaml.safe_load(f)

    model = conceptual_model(component_data)

    model.optimize()
    model.stores_t.e.plot()
    model.links_t.p0.plot()

    plt.show()
