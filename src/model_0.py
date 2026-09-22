import matplotlib.pyplot as plt
import numpy as np
import os
import time

import pypsa

"""Simple modelling of BECCS and DACCS co2 value chains.
    Functions:
    - conceptual model(): 
        - Contains all model components: atmosphere, biomass supply, co2 harbor storage, chp+ccs, co2 road and rail transport
        - but also contains: loads for heat and electricity, heat vent
    - model_optimization_and_plot_1()
        - Contains constrains and the objective of the optimization and manages the saving or displaying of the figures
    """


def conceptual_model(model_parameter, snapshots=24):

    mp = model_parameter

    n = pypsa.Network()
    n.set_snapshots(range(snapshots))

    # Atmosphere
    n.add("Carrier", "co2 atmosphere", co2_emissions=-1.0)
    n.add("Bus", "co2 atmosphere", carrier="co2 atmosphere", unit="t_co2")
    n.add("Store", "co2 atmosphere",
        e_nom=np.inf,
        e_min_pu=-1,
        carrier="co2 atmosphere",
        bus="co2 atmosphere",
        )

    # Biomass: Initial biomass is set in the store, and a generator is added to represent the supply of biomass.
    n.add("Carrier", "solid biomass")
    n.add("Bus", "solid biomass dealer", carrier="solid biomass", unit="t_biomass")
    n.add("Store", "solid biomass",
        e_nom_extendable=True,
        e_initial=mp["biomass_potential"],
        carrier="solid biomass",
        bus="solid biomass dealer",
        marginal_cost=mp["biomass_mc"] #biomass price
        )

    n.add("Generator", "biomass supply",
        bus="solid biomass dealer",
        carrier="solid biomass",
        p_nom_extendable=True,
        p_nom_max=mp["biomass_potential"]
        )


    # co2 harbor and offshore storage
    n.add("Carrier", "co2 captured")
    n.add("Bus", "co2 captured", carrier="co2 captured", unit="t_co2")
    n.add("Store", "co2 captured harbor",
        e_nom_extendable=True,
        carrier="co2 captured",
        bus="co2 captured",
        capital_cost=mp["co2_store_harbor_cc"],
        )

    n.add("Bus", "co2 stored offshore", carrier="co2 stored offshore")
    n.add("Store", "co2 stored offshore",
        e_nom=mp["offshore_storage_capacity"],
        carrier="co2 stored offshore",
        bus="co2 stored offshore"
        )


    # CHP+CCS plant, local storage
    n.add("Carrier", "electricity")
    n.add("Bus", "electricity", carrier="electricity")
    n.add("Carrier", "heat")
    n.add("Bus", "heat", carrier="heat")
    n.add("Carrier", "co2 captured chp")
    n.add("Bus", "co2 captured chp", carrier="co2 captured chp", unit="t_co2")
    #n.add("Carrier", "solid biomass chp feed")
    n.add("Bus", "solid biomass chp feed", carrier="solid biomass", unit="t_biomass")

    n.add("Link", "CHP+CCS",
            bus0="solid biomass chp feed", bus1="electricity", bus2="heat", bus3="co2 atmosphere", bus4="co2 captured chp",
            efficiency=mp["chpccs_electric_eff"], efficiency2=mp["chpccs_thermal_eff"], efficiency3=mp["chpccs_co2_emissions"], efficiency4=mp["chpccs_co2_captured"],
            p_nom_extendable=True, capital_cost=mp["chpccs_cc"], marginal_cost=mp["chpccs_mc"]
            )
    
    n.add("Store", "co2 captured chp",
        e_nom=np.inf,
        carrier="co2 captured chp",
        bus="co2 captured chp"
        )


    # Loads
    n.add("Load", "heat load", bus="heat", p_set=mp["heat_load"])
    n.add("Load", "electricity load", bus="electricity", p_set=mp["electricity_load"])


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
        marginal_cost=-mp["electricity_market_price"],  # Electricity still generates income
        )


    # Land transport to harbor, assumed 1000km
    n.add("Link", "co2 rail transport",
        bus0="co2 captured chp", bus1="co2 captured", bus2="electricity",
        efficiency=mp["co2_rail_t_eff"], efficiency2=mp["co2_rail_t_el_consum"],
        p_nom_extendable=True, marginal_cost=mp["co2_rail_t_mc"]
        )

    n.add("Link", "co2 road transport",
          bus0="co2 captured chp", bus1="co2 captured", bus2="co2 atmosphere",
          efficiency=mp["co2_road_t_eff"], efficiency2=mp["co2_road_t_co2_emissions"],
          p_nom_extendable=True, marginal_cost=mp["co2_road_t_mc"]
          )


    # Sea transport from harbor to offshore co2 storage, assumed 1000km
    n.add("Link", "co2 ship transport",
          bus0="co2 captured", bus1="co2 stored offshore", bus2="co2 atmosphere",
          efficiency=mp["co2_ship_t_eff"], efficiency2=mp["co2_ship_t_co2_emissions"],
          p_nom_extendable=True, marginal_cost=mp["co2_ship_t_mc"]
          )

    n.add("Link", "co2 pipeline offshore transport",
          bus0="co2 captured", bus1="co2 stored offshore",
          efficiency=mp["co2_pipeline_offshore_t_eff"],
          p_nom_extendable=True, capital_cost=mp["co2_pipeline_offshore_t_cc"]
          )


    # Transport of biomass, assumed 100km
    n.add("Link", "biomass rail transport",
        bus0="solid biomass dealer", bus1="solid biomass chp feed", bus2="electricity",
        efficiency=mp["biomass_rail_t_eff"], efficiency2=mp["biomass_rail_t_el_consum"],
        p_nom_extendable=True, marginal_cost=mp["biomass_rail_t_mc"]
        )

    n.add("Link", "biomass road transport",
            bus0="solid biomass dealer", bus1="solid biomass chp feed", bus2="co2 atmosphere",
            efficiency=mp["biomass_road_t_eff"], efficiency2=mp["biomass_road_t_co2_emissions"],
            p_nom_extendable=True, marginal_cost=mp["biomass_road_t_mc"]
            )

    return n


def model_optimization_and_plot(model, save_path, show_or_save="show"):

    m = model

    #ToDo: Add constraint that requires the "co2 captured chp" store to be 0 in the last snapshot
    #m.add_constraints()

    status, condition = m.optimize()

    if condition == "optimal":
        stores_ax = m.stores_t.e.plot()
        links_ax = m.links_t.p0.plot()
        generators_ax = m.generators_t.p.plot()
        if show_or_save == "show":
            plt.show()
        elif show_or_save == "save":
            for name, ax in {"stores": stores_ax, "links": links_ax, "generators": generators_ax}.items():
                ax.figure.savefig(f"{save_path}/{name}.png", dpi=300)
        plt.close()
    else:
        print(f"Optimization failed: {status}, {condition}")



if __name__ == "__main__":

    save_path = f"output_data/{int(time.time())}"
    os.makedirs(save_path, exist_ok=True)

    model_parameter = {
        "electricity_load": 100, #MW/snapshot
        "heat_load": 100, #MW/snapshot
        "electricity_market_price": 10, #€/MWh
        "biomass_potential": 1000,   #MWh of biomass available in every snapshot (generator) and initially (store)
        "biomass_mc": 30, #€/MWh_biomass
        "co2_rail_t_mc":10, # €/t_co2 transported, 1000km of transport assumed
        "co2_store_harbor_cc": 1000,  # €/t_co2 capacity
        "chpccs_electric_eff": 0.35, #MWh_el / MWh_biomass
        "chpccs_thermal_eff": 0.5, #MWh_th / MWh_biomass
        "chpccs_co2_emissions": 0.0345, #t_co2 / MWh_biomass
        "chpccs_co2_captured": 0.1955, #t_co2 / MWh_biomass
        "chpccs_cc": 10000, #€/MW_biomass
        "chpccs_mc": 300, #€/MWh_biomass
        "co2_rail_t_eff": 1, #No losses during transport
        "co2_rail_t_el_consum": -0.035, #MWh/t_co2, 1000km of transport assumed
        "co2_road_t_eff":1, #No losses during transport
        "co2_road_t_co2_emissions": 0.08, #t_co2 emitted / t_co2 transported
        "co2_road_t_mc": 1500, # €/t_co2 transported, 1000km of transport assumed
        "offshore_storage_capacity": 6e6, #t_co2
        "co2_ship_t_eff": 1, #No losses during transport
        "co2_ship_t_co2_emissions": 0.0243, #ton_co2 emitted / t_co2 transported
        "co2_ship_t_mc": 10, # € / ton_co2 transported, 1000km of transport assumed
        "co2_pipeline_offshore_t_eff": 1, #No losses during transport
        "co2_pipeline_offshore_t_cc": 2400000, #€, 1000km of transport assumed
        "biomass_rail_t_eff": 1, #No losses during transport
        "biomass_rail_t_el_consum": -0.0035, #MWh/t_biomass, 100km of transport assumed
        "biomass_rail_t_mc": 1, # €/t_biomass transported, 100km of transport assumed
        "biomass_road_t_eff": 1, #No losses during transport
        "biomass_road_t_co2_emissions": 0.008, #t_co2 emitted / t_biomass transported, 100km assumed
        "biomass_road_t_mc": 150, # €/t_biomass transported, 100km of transport assumed
    }

    model = conceptual_model(model_parameter)
    
    model_optimization_and_plot(model, save_path)