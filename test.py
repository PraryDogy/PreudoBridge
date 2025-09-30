from system.database import Dbase, Clmns


Dbase.init()

values = {
    Clmns.partial_hash.name: 1
}

print(values)