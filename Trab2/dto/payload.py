from dataclasses import dataclass

import json

@dataclass
class Payload:
    row_id: int
    column_id: int
    row: list[int]
    column: list[int]
    result: int | None

    def to_dict(self) -> dict:
        return{ 
            'row_id': self.row_id,
            'colum_id': self.column_id,
            'row': self.row,
            'column': self.list,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @staticmethod
    def from_dict(data: dict) -> 'Payload':
        return Payload(**data)
    
    @staticmethod
    def from_json(data: str) -> 'Payload':
        return Payload.from_dict(json.loads(data))