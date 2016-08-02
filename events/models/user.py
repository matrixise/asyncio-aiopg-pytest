import sqlalchemy as sa

from . import meta

User = sa.Table(
    'users',
    meta,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.PrimaryKeyConstraint('id', name='users_id_pk')
)