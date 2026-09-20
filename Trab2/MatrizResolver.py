"""
Classe destinada unicamente a resolução das operações de multiplicação das matrizes 
"""

from dto.payload import Payload

class MatrixResolver:

    def validating_the_matrix_pair(self, first_matrix: list[list[int]], second_matrix: list[list[int]]) -> bool:
        """Valida se é possível realizar a operação de multiplicação das matrizes"""

        first_matrix_columns_length = len(first_matrix[0])
        second_matrix_rows_length = len(second_matrix)
        
        if first_matrix_columns_length == second_matrix_rows_length:
            return True
        
        return False
    
    
    def multiply_column_by_row(self, payload: Payload) -> int:
        """Devolve o resultado da multiplicação da linha pela coluna"""

        first_matrix_row = payload.row
        second_matrix_column = payload.column

        result = 0

        for i in range(len(first_matrix_row)):
            result += (first_matrix_row[i] * second_matrix_column[i])

        return result
    
    def build_matrix_result(
        self, 
        current_result_matrix: list[list[int]], 
        new_value: int, 
        row_id: int,
        column_id: int,
    ) -> list[list[int]]:
        """
            current_result_matrix: A matriz em seu estado atual
            new_value: Novo valor a ser inserido
            row_id: Posição da linha dentro da primeira matriz
            column_id: Posição da coluna dentro da segunda matriz
        """

        if not (0 <= row_id < len(current_result_matrix)):
            raise IndexError(f"row_id {row_id} fora da matriz resultado")
        if not (0 <= column_id < len(current_result_matrix[0])):
            raise IndexError(f"column_id {column_id} fora da matriz resultado")

        position_is_empty = current_result_matrix[row_id][column_id] is None

        if not position_is_empty:
            raise ValueError(
                f"Posição ({row_id}, {column_id}) já preenchida com "
                f"{current_result_matrix[row_id][column_id]}, recebido {new_value}"
            )
        
        current_result_matrix[row_id][column_id] = new_value
        return current_result_matrix