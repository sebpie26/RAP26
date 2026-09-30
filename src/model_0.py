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

    ToDo:
    - Change model parameters to realistic values
    - Model components more realistically
    - Develop a case study (distances, etc.)
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

    n.add("Generator", "solid biomass supply",
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

    n.add("Carrier", "co2 stored offshore")
    n.add("Bus", "co2 stored offshore", carrier="co2 stored offshore")
    n.add("Store", "co2 stored offshore",
        e_nom=mp["offshore_storage_capacity"],
        carrier="co2 stored offshore",
        bus="co2 stored offshore"
        )


    # chp+ccs plant, local storage
    n.add("Carrier", "electricity")
    n.add("Bus", "electricity", carrier="electricity")
    n.add("Carrier", "heat")
    n.add("Bus", "heat", carrier="heat")
    n.add("Carrier", "co2 captured chp")
    n.add("Bus", "co2 captured chp", carrier="co2 captured chp", unit="t_co2")
    #n.add("Carrier", "solid biomass chp feed")
    n.add("Bus", "solid biomass chp feed", carrier="solid biomass", unit="t_biomass")

    n.add("Link", "chp+ccs",
            bus0="solid biomass chp feed", bus1="electricity", bus2="heat", bus3="co2 atmosphere", bus4="co2 captured chp",
            efficiency=mp["chpccs_electric_eff"], efficiency2=mp["chpccs_thermal_eff"], efficiency3=mp["chpccs_co2_emissions"], efficiency4=mp["chpccs_co2_captured"],
            p_nom_extendable=True, capital_cost=mp["chpccs_cc"], marginal_cost=mp["chpccs_mc"]
            )
    
    n.add("Store", "co2 captured chp",
        e_nom=np.inf,
        carrier="co2 captured chp",
        bus="co2 captured chp"
        )

    # DAC, heat alternatively provided by a heatpump
    n.add("Bus", "co2 captured dac", carrier="co2 captured dac", unit="t_co2")
    n.add("Store", "co2 captured dac",
        e_nom=np.inf,
        carrier="co2 captured chp",
        bus="co2 captured chp"
        )
    
    n.add("Link", "dac",
            bus0="co2 atmosphere", bus1="co2 captured dac", bus2="electricity", bus3="heat",
            efficiency=mp["dac_capture_eff"], efficiency2=mp["dac_electricity_consum"], efficiency3=mp["dac_heat_consum"],
            p_nom_extendable=True, captial_cost=mp["dac_cc"]
            )
    n.add("Link", "heat pump dac",
          bus0="electricity", bus1="heat",
          efficiency=mp["heat_pump_COP"],
          p_nom_extendable=True, capital_cost=mp["heat_pump_cc"]
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
    for start in ["chp", "dac"]:
        n.add("Link", f"co2 rail transport {start}",
            bus0=f"co2 captured {start}", bus1="co2 captured", bus2="electricity",
            efficiency=mp["co2_rail_t_eff"], efficiency2=mp["co2_rail_t_el_consum"],
            p_nom_extendable=True, marginal_cost=mp["co2_rail_t_mc"]
            )

        n.add("Link", f"co2 road transport {start}",
            bus0=f"co2 captured {start}", bus1="co2 captured", bus2="co2 atmosphere",
            efficiency=mp["co2_road_t_eff"], efficiency2=mp["co2_road_t_co2_emissions"],
            p_nom_extendable=True, marginal_cost=mp["co2_road_t_mc"]
            )

        n.add("Link", f"co2 pipeline onshore transport {start}",
                bus0=f"co2 captured {start}", bus1="co2 captured",
                efficiency=mp["co2_pipeline_onshore_t_efficiency"],
                p_nom_extendable=True, capital_cost=mp["co2_pipeline_onshore_t_cc"]
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
    m.optimize.create_model()

    # Constraint that all co2 stores but the offshore store must be empty in the last snapshot
    stores_to_empty = ["co2 captured chp", "co2 captured dac", "co2 captured harbor"]
    m.model.add_constraints(m.model.variables.Store_e.loc[m.snapshots[-1], stores_to_empty] == 0, name="final_snapshot_conshore_stores_empty")

    # Constraint that DAC must remove at least 10 tons of co2 from the atmosphere in every snapshot
    dac_capture = m.model.variables.Link_p.sel(name="dac") * m.links.at["dac", "efficiency"]
    m.model.add_constraints(dac_capture >= 10, name="min_dac_capture_per_snapshot")

    # Track the combined CO2 store state at each snapshot.
    co2_store_names = ["co2 stored offshore", "co2 atmosphere"]
    total_co2_emitted = m.model.add_variables(coords=[m.snapshots], dims=["snapshot"], name="total_co2_emitted")
    m.model.add_constraints(total_co2_emitted == m.model.variables.Store_e.loc[:, co2_store_names].sum("name"),
        name="define_total_co2_emitted")


    status, condition = m.optimize.solve_model(solver_name="gurobi")


    if condition == "optimal":
        co2_stores = ["co2 atmosphere", "co2 captured harbor", "co2 stored offshore", "co2 captured chp", "co2 captured dac",]
        co2_stores_ax = plt.figure().add_subplot()
        m.stores_t.e[co2_stores].plot(ax=co2_stores_ax)
        m.model.variables["total_co2_emitted"].solution.to_pandas().plot(ax=co2_stores_ax, label="total co2 emitted")

        co2_transport_links = [link for link in m.links_t.p0 if "co2" in link and "transport" in link]
        co2_transport_links_ax = m.links_t.p0[co2_transport_links].plot()

        co2_sources_ax = plt.figure().add_subplot()
        m.links_t.p4["chp+ccs"].plot(ax=co2_sources_ax, label="chp with ccs")
        m.links_t.p1["dac"].plot(ax=co2_sources_ax, label="dac")

        #generators_ax = m.generators_t.p.plot()

        plot_dict = {"co2_stores": co2_stores_ax,
                    "co2_transport_links": co2_transport_links_ax,
                    "co2_sources": co2_sources_ax}

        for name, ax in plot_dict.items():
            ax.set(
                title=name.replace("_", " "),
                ylabel="ton co2",
                xlabel="hours")
            ax.grid(True)
            ax.legend()

        if show_or_save == "show":
            plt.show()
        elif show_or_save == "save":
            for name, ax in plot_dict.items():
                ax.figure.savefig(f"{save_path}/{name}.png", dpi=300)
        
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
        "chpccs_co2_emissions": -0.161, # 0.0345 - 0.1955 t_co2 / MWh_biomass
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
        "co2_pipeline_onshore_t_efficiency": 1, #No losses during transport
        "co2_pipeline_onshore_t_cc": 2000000, #€, 1000km of transport assumed
        "dac_capture_eff": 1, # Not captured co2 is immediatly released to the atmosphere
        "dac_electricity_consum": -0.35, # MWh_el / ton_co2 captured
        "dac_heat_consum": -2, # MWh_th / ton_co2 captured
        "dac_cc": 8, #€/ ton_co2 captured
        "heat_pump_COP": 3, #coefficient of performance
        "heat_pump_cc": 200000, #€ / MWh_el consumed
    }

    model = conceptual_model(model_parameter)
    
    model_optimization_and_plot(model, save_path)