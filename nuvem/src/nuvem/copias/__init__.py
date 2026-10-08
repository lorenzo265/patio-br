"""As cópias do banco e a restauração de teste (SDD 7.2, D-74).

Uma vez por dia, depois das 3h de Brasília, o worker faz a cópia do banco (``pg_dump``) direto
para o balde das cópias; uma vez por mês, volta a última num banco temporário e confere.
"""
