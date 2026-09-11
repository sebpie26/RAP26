""" Carbon management exaple from pypsa"""

import matplotlib.pyplot as plt
import pypsa

n = pypsa.Network()
n.set_snapshots(range(10))

n.add("Bus", "electricity")
n.add("Load", "load", bus="electricity", p_set=1)

n.add("Bus", "transport")
n.add("Load", "transport", bus="transport", p_set=1)

n.add("Bus", "diesel")
n.add("Store", "diesel", bus="diesel", e_cyclic=True, e_nom=1000)

n.add("Bus", "hydrogen")
n.add("Store", "hydrogen", bus="hydrogen", e_cyclic=True, e_nom=1000)


n.add(
    "Link", 
    "electrolysis", 
    p_nom=2.0, 
    efficiency=0.8, 
    bus0="electricity", 
    bus1="hydrogen"
)


n.add("Carrier", "co2", co2_emissions=-1)

n.add("Bus", "co2 atmosphere", carrier="co2")
n.add("Store", 
      "co2 atmosphere", 
      e_nom=1000, 
      e_min_pu=-1, #Full capacity can also be used to withdraw emissions
      bus="co2 atmosphere")

n.add("Bus", "co2 stored")
n.add("Store", "co2 stored", e_nom=1000, e_min_pu=-1, bus="co2 stored")


n.add(
    "Link", 
    "Fischer-Tropsch", 
    p_nom=4, 
    bus0="hydrogen", 
    bus1="diesel", 
    bus2="co2 stored", 
    efficiency=1, 
    efficiency2=-1
)


n.add(
    "Link", 
    "DAC", 
    bus0="electricity", 
    bus1="co2 stored", 
    bus2="co2 atmosphere", 
    efficiency=1, 
    efficiency2=-1, 
    p_nom=5
)


n.add(
    "Link",
    "diesel car",
    bus0="diesel",
    bus1="transport",
    bus2="co2 atmosphere",
    efficiency=1,
    efficiency2=1,
    p_nom=2,
)


n.add("Bus", "gas")

n.add("Store", "gas", e_initial=50, e_nom=50, marginal_cost=20, bus="gas")

n.add(
    "Link",
    "OCGT",
    bus0="gas",
    bus1="electricity",
    bus2="co2 atmosphere",
    p_nom_extendable=True,
    efficiency=0.5,
    efficiency2=1,
)

n.add(
    "Link",
    "OCGT+CCS",
    bus0="gas",
    bus1="electricity",
    bus2="co2 stored",
    bus3="co2 atmosphere",
    p_nom_extendable=True,
    efficiency=0.4,
    efficiency2=0.9,
    efficiency3=0.1,
)

n.add("Bus", "biomass")

n.add(
    "Store",
    "biomass",
    bus="biomass",
    marginal_cost=30,
    e_nom=55,
    e_initial=55,
)

n.add(
    "Link",
    "biomass",
    bus0="biomass",
    bus1="electricity",
    p_nom_extendable=True,
    capital_cost=1,
    efficiency=0.5,
)

n.add(
    "Link",
    "biomass+CCS",
    bus0="biomass",
    bus1="electricity",
    bus2="co2 stored",
    bus3="co2 atmosphere",
    p_nom_extendable=True,
    capital_cost=1,
    efficiency=0.4,
    efficiency2=1,
    efficiency3=-1,
)


n.add(
    "GlobalConstraint",
    "co2_limit",
    sense="<=",
    constant=-50,
)


n.optimize()

n.stores_t.e.plot()
n.links_t.p0.plot()

plt.show()