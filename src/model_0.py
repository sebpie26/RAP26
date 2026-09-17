import matplotlib.pyplot as plt
import numpy as np

import pypsa


def conceptual_model(model_parameter, snapshots=24):

    mp = model_parameter

    n = pypsa.Network()
    n.set_snapshots(range(snapshots))

    # Atmosphere
    n.add("Carrier", "co2", co2_emissions=-1.0)
    n.add("Bus", "co2 atmosphere", carrier="co2", unit="t_co2")
    n.add("Store", "co2 atmosphere",
        e_nom=np.inf,
        e_min_pu=-1,
        carrier="co2",
        bus="co2 atmosphere",
    )

    # Biomass: Initial biomass is set in the store, and a generator is added to represent the supply of biomass.
    n.add("Carrier", "solid biomass")
    n.add("Bus", "solid biomass", carrier="solid biomass")
    n.add("Store", "solid biomass",
        e_nom=np.inf,
        e_initial=mp["biomass_potential"],
        carrier="solid biomass",
        bus="solid biomass",
        marginal_cost=30) #biomass price
    
    n.add("Generator", "biomass supply",
        bus="solid biomass",
        carrier="solid biomass",
        p_nom_extendable=True,
        p_nom_max=mp["biomass_potential"],
        marginal_cost=30) #biomass price


    # co2 storage
    n.add("Carrier", "co2 captured")
    n.add("Bus", "co2 captured", carrier="co2 captured", unit="t_co2")
    n.add("Store", "co2 captured",
        e_nom=np.inf,
        carrier="co2 captured",
        bus="co2 captured",
        marginal_cost=0,
    )


    # CHP+CCS plant
    n.add("Carrier", "electricity")
    n.add("Bus", "electricity", carrier="electricity")
    n.add("Carrier", "heat")
    n.add("Bus", "heat", carrier="heat")

    n.add("Link", "CHP+CCS",
            bus0="solid biomass", bus1="electricity", bus2="heat", bus3="co2 atmosphere", bus4="co2 captured",
            efficiency=0.35, efficiency2=0.5, efficiency3=0.0345, efficiency4=0.1955,
            p_nom_extendable=True, capital_cost=10000, marginal_cost=30)


    # Loads
    n.add("Load", "heat load", bus="heat", p_set=100)
    n.add("Load", "electricity load", bus="electricity", p_set=100)


    # Heat vent and electricity vent to not violate the energy balance (chp out = load).
    n.add("Generator", "heat vent",
        bus="heat",
        carrier="heat",
        p_nom_extendable=True,
        p_max_pu=0,
        p_min_pu=-1,
    )

    n.add("Generator", "electricity vent",
        bus="electricity",
        carrier="electricity",
        p_nom_extendable=True,
        p_max_pu=0,
        p_min_pu=-1,
        marginal_cost=-10,  # Electricity still generates income
    )




    return n


if __name__ == "__main__":

    model_parameter = {
        "biomass_potential": 1000   #MWh of biomass available in every snapshot (generator) and initially (store)
    }

    model = conceptual_model(model_parameter)

    model.optimize()

    model.stores_t.e.plot()
    model.links_t.p0.plot()
    model.generators_t.p.plot()


    plt.show()