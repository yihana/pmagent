from db.session import engine, Base
from db import models  # noqa
if __name__ == '__main__':
    Base.metadata.create_all(bind=engine)
    print('DB tables created.')