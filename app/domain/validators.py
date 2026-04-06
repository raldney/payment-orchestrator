import re

CPF_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
CNPJ_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def validate_tax_id(tax_id: str) -> bool:
    digits = re.sub("\\D", "", tax_id)
    if len(digits) == 11:
        return _validate_cpf(digits)
    elif len(digits) == 14:
        return _validate_cnpj(digits)
    return False


def _validate_cpf(digits: str) -> bool:
    if digits == digits[0] * 11:
        return False
    for i in range(9, 11):
        value = sum(int(digits[num]) * (i + 1 - num) for num in range(i))
        check = value * 10 % 11 % 10
        if check != int(digits[i]):
            return False
    return True


def _validate_cnpj(digits: str) -> bool:
    if digits == digits[0] * 14:
        return False
    for i in [12, 13]:
        weights = CPF_WEIGHTS if i == 12 else CNPJ_WEIGHTS
        value = sum(int(digits[num]) * weights[num] for num in range(i))
        check = 11 - value % 11
        if check >= 10:
            check = 0
        if check != int(digits[i]):
            return False
    return True
