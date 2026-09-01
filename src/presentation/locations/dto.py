from pydantic import BaseModel, ConfigDict


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str
    address: str


class SeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: int
    sector: str
    row: int
    number: int
    x: int  # noqa: WPS111
    y: int  # noqa: WPS111


class LocationDetail(BaseModel):
    location: LocationRead
    seats: list[SeatRead]
