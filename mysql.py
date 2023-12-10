import pymysql, json, enum
from datetime import datetime
from typing import Callable, Iterable, Generic, TypeVar, Union, Any, overload
from typing_extensions import Self


# == SESSION == #
class _Session:
    query: str = ''

    def __init__(self, host, user, password, database, charset="utf8") -> None:
        self.conn = None
        self.kwargs = dict(
            host=host,
            user=user,
            password=password,
            database=database,
            charset=charset
        )

    def connect(self) -> Self:
        self.conn = pymysql.connect(**self.kwargs)
        self.cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        return self

    def execute(self, query: str, commit: bool = False) -> None:
        try:
            print(f'OK, Affected rows: {self.cursor.execute(query)}')
            _Session.query = query
            if commit:
                self.conn.commit()
        except AttributeError:
            raise RuntimeError("Session is not connected")
        except Exception as e:
            print(query)
            raise e

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


_sessions: list[_Session | None] = [None]

def set_session(host, user, password, database, charset="utf8") -> _Session:
    _sessions[0] = _Session(host, user, password, database, charset)
    return _sessions[0]


# == DATA TYPES == #
class DataType:
    def __init__(self, size: int) -> None:
        self.size = size
        self.definition: str = ''
    
    def to_python(self, value: Any) -> Any:
        return value
    
    def to_sql(self, value: Any) -> Any:
        return "'%s'" % value
    
    def default_format(self, value: Any) -> str:
        return self.to_sql(value)


class StringType(DataType):
    def __init__(self, size: int, fixed: bool = False, convert: bool = True) -> None:
        super().__init__(size)
        self.definition = f'char({size})' if fixed else f'varchar({size})'

        if convert:
            self.to_python = lambda x: str(x)
    
    def to_sql(self, value: Any) -> Any:
        if isinstance(value, str):
            return "'{}'".format(value.replace("'", "\\'").replace('"', '\\"'))
        elif isinstance(value, bytes):
            return "'{}'".format(value.decode().replace("'", "\\'").replace('"', '\\"'))
        else:
            raise TypeError(f'Cannot convert {value} to SQL')


class TextType(DataType):
    def __init__(self, size: int, convert: bool = True) -> None:
        super().__init__(size)
        if size == 0:
            self.definition = "tinytext"
        elif size == 1:
            self.definition = "text"
        elif size == 2:
            self.definition = "mediumtext"
        elif size == 3:
            self.definition = "longtext"
        else:
            raise ValueError("size must be 0, 1, 2, or 3")

        if convert:
            self.to_python = lambda x: str(x)


_E = TypeVar("_E")

class EnumType(DataType, Generic[_E]):
    def __init__(self, enum_class: type[enum.Enum]) -> None:
        super().__init__(None)
        self.definition = f'enum({", ".join(map(self.to_sql, enum_class._member_names_))})'
        self.enum_class = enum_class

        self.to_python = lambda x: enum_class(x)

    def default_format(self, value: _E) -> str:
        return self.to_sql(str(value))


class SetType(DataType):
    def __init__(self, enum_class: type[enum.Enum], *values: str) -> None:
        super().__init__(None)
        to_sql_first: Callable[[str], str] = lambda x: "'%s'" % x
        self.definition = f'set({", ".join(map(to_sql_first, values))})'
        self.enum_class = enum_class

    def to_python(self, value: Any) -> Any:
        return list(map(self.enum_class, value.split(',')))

    def to_sql(self, value: Iterable[str] | str) -> Any:
        if isinstance(value, str):
            return "'%s'" % value
        elif isinstance(value, Iterable):
            return "'%s'" % ','.join(map(str, value))
        else:
            raise TypeError(f'Cannot convert {value} to SQL')


TINYINT = 1
"`IntegerType`: 1 byte, -128 to 127"
SMALLINT = 2
"`IntegerType`: 2 bytes, -32768 to 32767"
MEDIUMINT = 3
"`IntegerType`: 3 bytes, -8388608 to 8388607"
INT = 4
"`IntegerType`: 4 bytes, -2147483648 to 2147483647"
BIGINT = 8
"`IntegerType`: 8 bytes, -9223372036854775808 to 9223372036854775807"


class IntegerType(DataType):
    def __init__(
        self,
        size: int = INT,
        unsigned: bool = True,
        display: int = None,
        convert: bool = True
    ) -> None:
        super().__init__(size)
        if size == 1:
            if display:
                self.definition = f'tinyint({display})'
            else:
                self.definition = "tinyint"
                "tinyint: 1 byte, -128 to 127"
        elif size == 2:
            self.definition = "smallint"
        elif size == 3:
            self.definition = "mediumint"
        elif size == 4:
            self.definition = "int"
        elif size == 8:
            self.definition = "bigint"
        else:
            raise ValueError("size must be 1, 2, 3, 4, or 8")
        
        if unsigned:
            self.definition += " unsigned"

        if convert:
            self.to_python = lambda x: int(x)
        
        self.to_sql = lambda x: str(x)

    def default_format(self, value: int) -> str:
        return "'%d'" % value


class BooleanType(DataType):
    definition = "tinyint(1)"

    def __new__(cls) -> type[Self]:
        return cls

    @classmethod
    def to_python(cls, value: Any) -> bool:
        return bool(value)
    
    @classmethod
    def to_sql(cls, value: bool | int) -> Any:
        if isinstance(value, (int, bool)):
            return "TRUE" if value else "FALSE"
        else:
            raise TypeError(f'Cannot convert {value} to SQL')

    @classmethod
    def default_format(cls, value: bool) -> str:
        return cls.to_sql(value)


FLOAT = 4
"`FloatType`: 4 bytes, -3.402823466E+38F to 3.402823466E+38F"
DOUBLE = 8
"`FloatType`: 8 bytes, -1.7976931348623157E+308 to 1.7976931348623157E+308"


class FloatType(DataType):
    def __init__(self, size: int = 4, unsigned: bool = True, convert: bool = True) -> None:
        if size == 4:
            self.definition = "flaot"
        elif size == 8:
            self.definition = "double"
        else:
            raise ValueError("size must be 4 or 8")
        
        if unsigned:
            self.definition += " unsigned"
        
        if convert:
            self.to_python = lambda x: float(x)
        
        self.to_sql = lambda x: str(x)
    
    def default_format(self, value: float) -> str:
        return "'%f'" % value


class DecimalType(DataType):
    def __init__(self, size: int = 10, decimal: int = 0, unsigned: bool = True, convert: bool = True) -> None:
        super().__init__(size)
        self.definition = f'decimal({size}, {decimal})'
        
        if unsigned:
            self.definition += " UNSIGNED"

        if convert:
            self.to_python = lambda x: x

        self.to_sql = lambda x: str(x)


class BitType(DataType):
    def __init__(self, size: int = 1, convert: bool = True) -> None:
        super().__init__(size)
        self.definition = f'bit({size})'

        if convert:
            self.to_python = lambda x: int(x)
        
    def to_sql(self, value: int | bytes | str) -> str:
        if isinstance(value, int):
            return f'b\'{value:0{self.size}b}\''
        elif isinstance(value, bytes):
            return f'b\'{int.from_bytes(value, "big"):0{self.size}b}\''
        elif isinstance(value, str):
            return value
        else:
            raise TypeError(f'Cannot convert {value} to SQL')


class JsonType(DataType):
    definition = "json"

    def __new__(cls) -> type[Self]:
        return cls
    
    @classmethod
    def to_python(cls, value: Any) -> Any:
        return json.loads(value)
    
    @classmethod
    def to_sql(cls, value: Any) -> Any:
        return json.dumps(value)


class TimeStampType(DataType):
    def __init__(self, current_timestamp: bool = True) -> None:
        self.definition = "timestamp"

        if current_timestamp:
            self.definition += " DEFAULT CURRENT_TIMESTAMP"

    def to_python(self, value: Any) -> datetime:
        return datetime.fromisoformat(value)
    
    def to_sql(self, value: Any) -> str:
        if isinstance(value, datetime):
            return super().to_sql(value.isoformat())
        elif isinstance(value, str):
            return value
        elif isinstance(value, int):
            return f'FROM_UNIXTIME({value})'
        else:
            raise TypeError(f'Cannot convert {value} to SQL')


# == MODEL == #
class RawFormat:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


class _SelectQuery:
    def __init__(self, field: "_FieldBase" = None) -> None:
        if field is None:
            self.query = ''
        else:
            self.query = str(field)

    def __add__(self, __value: str | Self) -> Self:
        if isinstance(__value, str):
            self.query += __value
        elif isinstance(__value, _SelectQuery):
            self.query += str(__value)
        else:
            return NotImplemented
        return self

    def __eq__(self, __value: Any) -> Self:
        self.query += f' = {__value}'
        return self
    
    def __gt__(self, __value: Any) -> Self:
        self.query += f' > {__value}'
        return self
    
    def __lt__(self, __value: Any) -> Self:
        self.query += f' < {__value}'
        return self
    
    def __ge__(self, __value: Any) -> Self:
        self.query += f' >= {__value}'
        return self
    
    def __le__(self, __value: Any) -> Self:
        self.query += f' <= {__value}'
        return self
    
    def __ne__(self, __value: Any) -> Self:
        self.query += f' != {__value}'
        return self
    
    def __str__(self) -> str:
        return self.query
    
    def __and__(self, __value: Any) -> Self:
        self.query += f' AND {__value}'
        return self
    
    def __or__(self, __value: Any) -> Self:
        self.query += f' OR {__value}'
        return self
    
    def __invert__(self) -> Self:
        self.query = f'NOT {self.query}'
        return self

    def __call__(self, *args) -> Self:
        self.query += f'({", ".join(map(lambda x: "`%s`" % x, args))})'
        return self

    def __contains__(self, __value: Any) -> Self:
        if isinstance(__value, str):
            self.query += f' LIKE "%{__value}%"'
        elif isinstance(__value, Iterable):
            self.query += f' IN ({", ".join(map(str, __value))})'
        return self

    def __iter__(self) -> Iterable[str]:
        return iter(self.query.split())
    
    def __len__(self) -> int:
        return len(self.query.split())

    def from_(self, table: type["Model"]) -> Self:
        self.query += f' FROM {table.__name__}'
        return self
    
    def join(self, table: type["Model"]) -> Self:
        self.query += f' INNER JOIN {table.__name__}'
        return self
    
    def on(self, condition: Self) -> Self:
        self.query += f' ON {condition}'
        return self

    def where(self, condition: Self) -> Self:
        self.query += f' WHERE {condition}'
        return self

    def group_by(self, *args: "_FieldBase") -> Self:
        self.query += f' GROUP BY {", ".join(map(str, args))}'
        return self

    def having(self, condition: Self) -> Self:
        self.query += f' HAVING {condition}'
        return self
    
    def order_by(self, field: "_FieldBase", descending: bool = None) -> Self:
        self.query += f' ORDER BY {field}'
        if descending:
            self.query += ' DESC'
        return self
    
    def limit(self, limit: int) -> Self:
        self.query += f' LIMIT {limit}'
        return self

    def offset(self, offset: int) -> Self:
        self.query += f' OFFSET {offset}'
        return self

    def execute(self):
        _sessions[0].execute(self.query + ';')
        return _sessions[0].cursor


def select(*args: Union[RawFormat, "_FieldBase"]) -> _SelectQuery:
    query = _SelectQuery() + "SELECT "

    if args:
        if isinstance(args[0], RawFormat):
            query += args[0].value
        else:
            for field in args:
                if isinstance(field, _FieldBase):
                    query += field.name + ", "
                else:
                    raise TypeError(f'{field} is not a field')
            query.query = query.query[:-2]
    else:
        query += '*'
    return query


class _FieldBase:
    def __init__(self, *, pk: bool, nullable: bool, default: Any, name: str) -> None:
        self.name = name

        if nullable and not pk:
            if default is None:
                self.definition += "DEFAULT NULL "
            elif isinstance(default, RawFormat):
                self.definition += f'DEFAULT {default.value} '
            else:
                self.definition += f'DEFAULT {self.type.default_format(default)} '
        else:
            self.definition += "NOT NULL "
            if isinstance(default, RawFormat):
                self.definition += f'DEFAULT {default.value} '
            elif default is not None:
                self.definition += f'DEFAULT {self.type.default_format(default)} '

    def __str__(self) -> str:
        return self.name

    def __eq__(self, __value: str | Self) -> bool:
        if isinstance(__value, str):
            return self.name == __value
        elif isinstance(__value, _FieldBase):
            return self.name == __value.name
        else:
            return False

    def __gt__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) > __value
    
    def __lt__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) < __value

    def __ge__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) >= __value
    
    def __le__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) <= __value
    
    def __ne__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) != __value
    
    def __and__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) & __value
    
    def __or__(self, __value: str | Self) -> _SelectQuery:
        return _SelectQuery(self) | __value
    
    def __invert__(self) -> _SelectQuery:
        return ~_SelectQuery(self)

    def __call__(self, *args) -> _SelectQuery:
        return _SelectQuery(self)(*args)

    def __contains__(self, __value: Any) -> _SelectQuery:
        return _SelectQuery(self) in __value

    def to_query(self) -> _SelectQuery:
        return _SelectQuery(self)


class Field(_FieldBase):
    def __init__(
        self,
        type: DataType,
        nullable: bool = True,
        pk: bool = False,
        unique: bool = False,
        default: RawFormat | Any = None,
        transform: Callable = None,
        *,
        auto_increament: bool = False,
        raw_args: Iterable[str] = (),
        name: str = None
    ) -> None:
        self.type = type
        self.default = default
        self.primary = pk
        self.unique = unique

        if transform is None:
            self.transform = type.to_python
        else:
            self.transform = lambda x: x

        self.definition = type.definition + ' '

        if auto_increament:
            self.definition += " AUTO_INCREMENT"

        super().__init__(pk=pk, nullable=nullable, default=default, name=name)

        for arg in raw_args:
            self.definition += arg + ' '

        self.definition = self.definition.removesuffix(' ')
        self.set_value = None

    def setter(self, func: Callable[[Any], None]) -> None:
        self.set_value = func


CASCADE = "CASCADE"
"`str`: Deletes or updates the row from the parent table and automatically delete or update the matching rows in the child table."
SET_NULL = "SET NULL"
"""`str`: Delete or update the row from the parent table and set the foreign key column or columns in the child table to NULL.
This is valid only if the foreign key columns do not have the NOT NULL qualifier specified."""
RESTRICT = "RESTRICT"
"""`str`: Rejects the delete or update operation for the parent table.
Specifying RESTRICT (or NO ACTION) is the same as omitting the ON DELETE or ON UPDATE clause."""


class ForeignKey(_FieldBase):
    def __init__(
        self,
        table: type["Model"],
        referenced_attr_name: str | None = None,
        nullable: bool = False,
        default: Any = None,
        *,
        on_update: str = CASCADE,
        on_delete: str = CASCADE,
        pk: bool = False,
        unique: bool = False,
        only_one: bool = True,
        name: str = None
    ) -> None:
        if referenced_attr_name is None:
            referenced_attr_name = table.primary_attr

        self.referenced_field: Field | ForeignKey = getattr(table, referenced_attr_name)
        "Union[`Field`, `ForeignKey`]: The name of the field that is referenced."
        self.referenced_attr_name: str = referenced_attr_name
        "`str`: The name of the attribute that is referenced."

        self.type = self.referenced_field.type
        self.definition = self.referenced_field.type.definition + ' '

        super().__init__(pk=pk, nullable=nullable, default=default, name=name)

        self.definition += f',\n\tFOREIGN KEY({referenced_attr_name}) REFERENCES {table.__name__}({self.referenced_field.name})'

        if on_delete:
            self.definition += f'\n\tON DELETE {on_delete}'
        if on_update:
            self.definition += f'\n\tON UPDATE {on_update}'

        self.table = table
        self.primary = pk
        self.unique = unique
        self.only_one = only_one


class _Undefiend: ...

_T = TypeVar("_T", bound="Model")


class _Records(Generic[_T]):
    def __init__(self, model: type["Model"]) -> None:
        self.model = model

    def __call__(self, **kwargs) -> _T:
        "Returns a new object created with the given kwargs."
        query = f'INSERT INTO {self.model.__name__} ('
        values = "VALUES ("

        for key, value in kwargs.items():
            query += f'{key}, '
            if (field := self.model.fields.get(key)) is None:
                raise ValueError(f'{key} is not a field')
            values += f'{field.type.to_sql(value)}, '
        query = query[:-2] + ") " + values[:-2] + ");"
        _sessions[0].execute(query)
        _sessions[0].conn.commit()
        return self.model(_sessions[0], kwargs)

    def _select_data(self, query: str | None = None, **kwargs) -> None:
        if query is None:
            query = f'SELECT * FROM {self.model.__name__} WHERE '

        for key, value in kwargs.items():
            query += f'{key} = \'{value}\' AND '
        query = query[:-5] + ";"
        _sessions[0].execute(query)

    @overload
    def get(self, **kwargs) -> _T | None:
        ...

    @overload
    def get(self, model: "Model", **kwargs) -> _T | None:
        ...

    def get(self, *args, **kwargs) -> _T | None:
        self._select_data(**kwargs)
        result = _sessions[0].cursor.fetchone()

        if result is None:
            return None

        if args and isinstance(args[0], Model):
            model = args[0]
            for fk in self.model.foreign_keys:
                if self.model.fields.get(fk.referenced_attr_name) is not None:
                    break
            else:
                raise ValueError(f'{self.model.__name__} is not a foreign key of {model.__class__.__name__}')
            return self.model(result, **{fk.referenced_attr_name: model})
        elif args:
            raise TypeError("First argument must be a Model")
        else:
            return self.model(result)
    
    @overload
    def filter(self, **kwargs) -> list[_T]:
        ...

    @overload
    def filter(self, model: "Model", **kwargs) -> list[_T]:
        ...

    def filter(self, *args, **kwargs) -> list[_T]:
        self._select_data(**kwargs)
        if args and isinstance(args[0], Model):
            model = args[0]
            for fk in self.model.foreign_keys:
                if model.fields.get(fk.referenced_attr_name) is not None:
                    break
            else:
                raise ValueError(f'{self.model.__name__} is not a foreign key of {model.__class__.__name__}')
            return [self.model(data, **{fk.referenced_attr_name: model}) for data in _sessions[0].cursor.fetchall()]
        elif args:
            raise TypeError("First argument must be a Model")
        else:
            return [self.model(data) for data in _sessions[0].cursor.fetchall()]

    def all(self) -> list[_T]:
        _sessions[0].execute(f'SELECT * FROM {self.model.__name__};')
        return [self.model(_sessions[0], data) for data in _sessions[0].cursor.fetchall()]

    def count(self, condition: _SelectQuery = _SelectQuery(), **kwargs) -> int:
        query = select(RawFormat("COUNT(*)")).from_(self.model)

        if kwargs:
            for key, value in kwargs.items():
                condition += f'{key} = {value} AND '

            query.query = query.query[:-5]

        query.where(condition)

        return query.execute().fetchone()['COUNT(*)']

    def update(self, **kwargs) -> None:
        query = f'UPDATE {self.model.__name__} SET '

        for key, value in kwargs.items():
            if (field := self.model.fields.get(key)) is None:
                raise ValueError(f'{key} is not a field')
            query += f'{key} = {field.type.to_sql(value)}, '
        query = query[:-2] + ";"
        _sessions[0].execute(query)
        _sessions[0].conn.commit()

    def get_or_create(self, **kwargs) -> _T:
        if (obj := self.get(**kwargs)) is None:
            obj = self(**kwargs)
        return obj

    def create_or_update(self, **kwargs) -> _T:
        query = f'INSERT INTO {self.model.__name__} ('
        values = "VALUES ("

        for key, value in kwargs.items():
            query += f'{key}, '
            if (field := self.model.fields.get(key)) is None:
                raise ValueError(f'{key} is not a field')
            values += f'{field.type.to_sql(value)}, '
        query = query[:-2] + ") " + values[:-2] + ") ON DUPLICATE KEY UPDATE "

        for key, value in kwargs.items():
            if (field := self.model.fields.get(key)) is None:
                raise ValueError(f'{key} is not a field')
            query += f'{key} = {field.type.to_sql(value)}, '
        query = query[:-2] + ";"
        _sessions[0].execute(query)
        _sessions[0].conn.commit()
        return self.model(_sessions[0], kwargs)


class _JoinedRecords(_Records, Generic[_T]):
    def get(self, *args, **kwargs) -> _T | None:
        super_model: type[Model] = self.model.__base__

        query = f'SELECT * FROM {self.model.__name__}'
        query += f'\nINNER JOIN {super_model.__name__} ON '

        for fk in self.model.foreign_keys_for_join:
            query += f'{self.model.__name__}.{fk.name} = {super_model.__name__}.{fk.referenced_attr_name} AND '
        query = query[:-5]

        query += f'\nWHERE '

        self._select_data(query, **kwargs)
        result = _sessions[0].cursor.fetchone()
        if result is None:
            return None

        return self.model(result)
    
    def filter(self, **kwargs) -> list[_T]:
        super_model: type[Model] = self.model.__base__

        query = f'SELECT * FROM {self.model.__name__}'
        query += f'\nINNER JOIN {super_model.__name__} ON '

        for fk in self.model.foreign_keys_for_join:
            query += f'{self.model.__name__}.{fk.name} = {super_model.__name__}.{fk.referenced_attr_name} AND '

        query = query[:-5]
        query += f'\nWHERE '
        self._select_data(query, **kwargs)

        return [self.model(data) for data in _sessions[0].cursor.fetchall()]
    
    def all(self) -> list[_T]:
        _sessions[0].execute(f'SELECT * FROM {self.model.__name__} {self.join};')
        return [self.model(_sessions[0], data) for data in _sessions[0].cursor.fetchall()]


class Model:
    fields: dict[str, Field | ForeignKey]
    primary_keys: list[Field | ForeignKey]
    "List[`Field` | `ForeignKey`]: The names of the primary keys."
    unique_keys: list[Field | ForeignKey]
    "List[`Field` | `ForeignKey`]: The names of the unique keys."
    foreign_keys: list[ForeignKey]
    "List[`ForeignKey`]: The names of the foreign keys."
    primary_attr: str
    "`str`: The name of the attribute that matchs the primary key."
    objects: _Records[Self] | _JoinedRecords[Self]
    "`_Records`: The objects of this model."
    foreign_keys_for_join: list[ForeignKey]
    "List[`ForeignKey`]: The foreign keys that are used for joining tables."

    def __init__(self, data: dict[str, Any] = {}, match: bool = True, **kwargs) -> None:
        self.matched: bool = False
        self.primary_data: dict[str, Any] = {}
        self.object: _Record = _Record(self)

        if match:
            self.match_attr(data, **kwargs)
        else:
            for attr in self.fields:
                setattr(self, attr, None)

        self.init()

    def __init_subclass__(cls, model: bool = True) -> None:
        cls.primary_keys = []
        cls.foreign_keys = []
        cls.unique_keys = []
        cls.primary_attr = None
        cls.fields = {}
        cls.foreign_keys_for_join = []

        super_cls: type[Model] = cls.__bases__[0]

        if issubclass(super_cls, Model) and super_cls is not Model:
            cls.primary_keys += super_cls.primary_keys
            cls.fields.update(super_cls.fields)
            cls.objects = _JoinedRecords(cls)
        else:
            cls.objects = _Records(cls)

        if model and cls.__name__ not in [c.__name__ for c in models]:
            models.append(cls)
            for attr in dir(cls):
                if isinstance(field := getattr(cls, attr), (Field, ForeignKey)):
                    field.name = field.name or attr

                    if isinstance(field, ForeignKey):
                        cls.foreign_keys.append(field)
                        temp = field.definition.split(',')
                        temp[1] = f'\n\tCONSTRAINT fk_{cls.__name__}_{field.name} ' + temp[1].removeprefix('\n\t')
                        field.definition = ','.join(temp)
                        if field.table is super_cls:
                            cls.foreign_keys_for_join.append(field)

                    cls.fields[attr] = field

                    if field.primary:
                        cls.primary_keys.append(field)
                        cls.primary_attr = attr
                    
                    if field.unique:
                        cls.unique_keys.append(field)

                    setattr(cls, attr, field)
        else:
            for attr in dir(super_cls):
                if not attr.startswith('__') and not attr.endswith('__'):
                    setattr(cls, attr, getattr(super_cls, attr))

    def __setattr__(self, __name: str, __value: Any) -> None:
        super().__setattr__(__name, __value)

        if self.matched and not __name.startswith('_'):
            field = self.fields.get(__name)

            if field is not None:
                if isinstance(field, Field) and field.set_value is not None:
                    field.set_value(__value)
                else:
                    self.object.update(**{__name: field.type.to_sql(__value)})

    def match_attr(self, data: dict[str, Any], **kwargs) -> Self:
        cls = self.__class__
        for attr in cls.fields:
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])
                continue
            field = cls.fields[attr]
            name = cls.fields[attr].name or attr
            if field.primary:
                self.primary_data[attr] = data[name]
            if isinstance(field, Field):
                value = data.get(name, _Undefiend)
                if value is _Undefiend:
                    field = self.undefined_field(field)
                    value = field.default
                field = field(value)
            elif isinstance(field, ForeignKey):
                _sessions[0].execute(f'SELECT * FROM {field.table.__name__} WHERE {field.referenced_field.name} = \'{data[name]}\'')
                arr = _sessions[0].cursor.fetchall()
                if field.only_one:
                    if arr:
                        field = field.table(arr[0], **{field.referenced_attr_name: self})
                    else:
                        field = None
                else:
                    field = [field.table(d, **{field.referenced_attr_name: self}) for d in arr]

            setattr(self, attr, field)

        return self

    def init(self) -> None:
        "Called after the object is created."
        pass

    def save(self) -> Self:
        kwargs = {}

        for attr_name, field in self.fields.items():
            kwargs[field.name or attr_name] = field.type.to_sql(getattr(self, attr_name))

        return self.objects.create_or_update(**kwargs)

    def undefined_field(self, field: Field):
        query = f'ALTER TABLE {self.__class__.__name__} ADD {field.name} {field.definition};'
        _sessions[0].execute(query)
        _sessions[0].conn.commit()
        return field


class _Record(_Records):
    def __init__(self, obj: Model) -> None:
        self.obj = obj
        super().__init__(obj.__class__)

    def get_value(self, field: str | Field, where: _SelectQuery = None) -> Any:
        if isinstance(field, Field):
            field = field.name

        query = select(field).from_(self.obj.__class__)

        if where:
            query += f' {where}'
        else:
            for key, value in self.obj.primary_data.items():
                query += f'{key} = {value} AND '

        return query.execute().fetchone()[field]

    def update(self, **kwargs) -> _T:
        query = f'UPDATE {self.__class__.__name__} SET '

        for key, value in kwargs.items():
            if (field := self.obj.fields.get(key)) is None:
                raise ValueError(f'{key} is not a field')
            if isinstance(value, RawFormat):
                query += f'{key} = {value.value}, '
            else:
                query += f'{key} = {field.type.to_sql(value)}, '
        query = query[:-2] + " WHERE "

        for key, value in self.obj.primary_data.items():
            query += f'{key} = {value} AND '
        query = query[:-5] + ";"
        _sessions[0].execute(query)
        _sessions[0].conn.commit()
        return self.obj
    
    def delete(self) -> None:
        query = f'DELETE FROM {self.obj.__class__.__name__} WHERE '

        for key, value in self.obj.primary_data.items():
            query += f'{key} = {value} AND '
        query = query[:-5] + ";"
        _sessions[0].execute(query)
        _sessions[0].conn.commit()


models: list[type[Model]] = []
"List[Type[`Model`]]: List of all tables in the database."


def _create_create_table_query(table: type[Model]) -> str:
    query = f'CREATE TABLE IF NOT EXISTS `{table.__name__}` (\n'

    for attr_name in table.__annotations__:
        field = getattr(table, attr_name, None)

        if isinstance(field, (Field, ForeignKey)):
            name = field.name or attr_name
            definition = field.definition
        else:
            continue
        query += f'\t{name} {definition},\n'
    query += f'\tPRIMARY KEY({", ".join(map(str, table.primary_keys))}),\n'
    query = query[:-2] + "\n);"
    return query


def create_tables() -> None:
    for table in models:
        query = _create_create_table_query(table)
        _sessions[0].execute(query)
        _sessions[0].conn.commit()


def _check_query(query: str | Iterable[str]) -> None:
    if isinstance(query, str):
        query = (query,)
    print(*query, sep='\n')
    rep = input("1). Execute\n2). Modify query\n3). Abort\n")
    if rep == '1':
        for q in query:
            _sessions[0].execute(q)
        _sessions[0].conn.commit()
    elif rep == '2':
        query = input("Query: ")
        _check_query(query)
    else:
        print("Aborted.")
        return

# TO DO: Add support for foreign keys
def migrate() -> None:
    try:
        for model in models:
            _sessions[0].execute(f'SHOW CREATE TABLE {model.__name__};')
            table_creation_query: str = _sessions[0].cursor.fetchone()['Create Table']
            field_names: list[str] = [''] * len(model.fields)
            different_attrs: dict[str, str] = {}
            different_columns: dict[str, str] = {}
            foreign_keys: dict[str, str] = {}
            definitions: dict[str, str] = {}
            other_definitions: list[str] = []
    
            for c_def in table_creation_query.split('\n')[1:-1]:
                if (_c_arr := c_def.strip().split())[0].startswith('`'):
                    definitions[_c_arr[0].strip('`')] = ' '.join(_c_arr[1:]).removesuffix(',')
                else:
                    other_definitions.append(' '.join(_c_arr).removesuffix(','))

            i = 0
            for field in model.fields.values():
                field_names[i] = field.name
                if isinstance(field, ForeignKey):
                    arr = field.definition.split(",\n\t")
                    fd = arr[0]
                    kd = arr[1]
                    if kd not in other_definitions:
                        foreign_keys[field.name] = kd.replace("\n\t", ' ')
                else:
                    fd = field.definition.strip()
                if fd != definitions.get(field.name):
                    different_attrs[field.name] = fd
                i += 1

            for col in definitions:
                if col not in field_names and col not in different_attrs:
                    different_columns[col] = definitions[col]

            print(table_creation_query) # This prints the query that creates the table
            queries = []
            query = f'ALTER TABLE {model.__name__}'

            if not (different_columns and different_attrs):
                continue

            for attr in different_attrs:
                prompt = f'Different attribute detected on `{model.__name__}`: `{attr}` {different_attrs[attr]}'
                print('-' * len(prompt))
                print(prompt)
                print('-' * len(prompt))

                if attr not in definitions:
                    print("< Different Column From Model >", '\n\t'.join([f'{k} {v}' for k, v in different_columns.items()]), sep="\n\t")
                    rep = input("1). Add new column\n2). Rename column\n3). Skip\n4). Abort\nNumber: ")
                    if rep == '1':
                        query += f'\n\tADD `{attr}` {different_attrs[attr]}'
                        print("< Other Columns >\n\t" + '\n\t'.join([f'`{k}` {v}' for k, v in definitions.items()]))
                        print("< Model Definition >\n\t" + '\n\t'.join([f'`{v.name}` {v.definition}' for v in model.fields.values()]))
                        pos = input("Column Position: ")
                        if pos == "FIRST":
                            query += " FIRST"
                        else:
                            if pos not in definitions:
                                raise ValueError("Invalid position")
                            query += f' AFTER {pos}'
                        pks = [pk.name for pk in model.primary_keys]
                        if attr in pks:
                            for pk in pks:
                                if pk != attr:
                                    _sessions[0].execute("SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME" 
                                        + "\nFROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE"
                                        + f'\nWHERE REFERENCED_TABLE_NAME = \'{model.__name__}\''
                                        + f'\nAND REFERENCED_COLUMN_NAME = \'{pk}\''
                                        + "\n;"
                                    )
                                    for fk in _sessions[0].cursor.fetchall():
                                        queries.append(f'ALTER TABLE {fk["TABLE_NAME"]}\n\tDROP KEY {fk["CONSTRAINT_NAME"]}\n;\n')
                            query += f',\n\tDROP PRIMARY KEY,\n\tADD PRIMARY KEY({", ".join(pks)})'
                    elif rep == '2':
                        column_to_rename = input("Column to rename: ")
                        query += f'\n\tCHANGE {column_to_rename} {attr} {different_attrs[attr]}'
                        del different_columns[column_to_rename]
                    elif rep == '3':
                        continue
                    else:
                        print("종료")
                        return
                else:
                    print(
                        "< Equal Name >",
                        f'CODE: `{attr}` {different_attrs[attr]}',
                        f'DB: `{attr}` {definitions[attr]}',
                        sep='\n'
                    )
                    rep = input("1). Modify column\n2). Skip\n3). Abort\n")
                    if rep == '1':
                        query += f'\n\tMODIFY `{attr}` {different_attrs[attr]}'
                    elif rep == '2':
                        continue
                    else:
                        print("종료")
                        return
                query += ','
            
            for col in different_columns:
                prompt = f'Different column detected on `{model.__name__}`: `{col}` {different_columns[col]}'
                print('-' * len(prompt))
                print(prompt)
                print('-' * len(prompt))
                rep = input("1). Rename column\n2). Drop column\n3). Skip\n4). Abort\nNumber: ")
                if rep == '1':
                    new_name = input("New name: ")
                    query += f'\n\tCHANGE `{col}` `{new_name}` {different_columns[col]}'
                elif rep == '2':
                    query += f'\n\tDROP `{col}`'
                elif rep == '3':
                    continue
                else:
                    print("종료")
                    return
                query += ','
            
            for fk in foreign_keys:
                prompt = f'Foreign key detected on `{model.__name__}`: {foreign_keys[fk]}'
                print('-' * len(prompt))
                print(prompt)
                print('-' * len(prompt))
                rep = input("1). Add Foreign Key\n2). Skip\n3). Abort\nNumber: ")
                if rep == '1':
                    query += f'\n\tADD {foreign_keys[fk]}'
                elif rep == '2':
                    continue
                else:
                    print("종료")
                    return
                query += ','

            queries.append(query.removesuffix(',') + "\n;")
            _check_query(queries)
    except KeyboardInterrupt:
        print("강제 종료")
        return

