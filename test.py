from sqlalchemy import func

from database import Cache, Dbase, Stats, sqlalchemy


def get_images_size() -> int:
    session = Dbase.get_session()
    q = func.sum(func.length(Cache.img))
    res = session.execute(q).scalar() or 0
    mb = round(res / (1024**2), 2)
    session.close()

    return res

def remove_excess_images(limit: int):
    session = Dbase.get_session()
    size = get_images_size()

    while size >= limit:

        q = sqlalchemy.select(Cache.id).order_by(Cache.id).limit(10)
        res = session.execute(q).all()

        for row in res:
            q = sqlalchemy.delete(Cache).where(Cache.id==row[0])
            session.execute(q)

        session.commit()
        size = get_images_size()

    q = sqlalchemy.text("VACUUM")
    session.execute(q)
    session.close()


gig_two = 2147483648
git_five = 5368709120
gig_ten = 10737418240
limit = 1000000

Dbase.init_db()
sess = Dbase.get_session()
