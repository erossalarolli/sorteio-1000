
# Sorteio 1–1000

Sistema de reserva de números com histórico de data/hora e proteção contra dupla reserva.

## Hospedagem gratuita no Render

1. Crie um repositório no GitHub e envie estes arquivos.
2. No Render, escolha **New → Blueprint** e conecte o repositório.
3. O `render.yaml` cria o Web Service + PostgreSQL.
4. Na configuração do serviço, defina `ADMIN_PASSWORD` para uma senha sua.
5. Aguarde o deploy.
6. O Render fornece uma URL `*.onrender.com`.

O painel administrativo fica em:
`https://SEU-LINK.onrender.com/admin`

## Importante

O PostgreSQL gratuito do Render atualmente expira após 30 dias. Para um sorteio de 1 dia funciona, mas não é uma solução para manter o histórico indefinidamente sem migrar o banco para um plano persistente.

A página pública aceita números 0001–1000. O banco possui UNIQUE(numero) e o INSERT usa conflito atômico, então em uma disputa simultânea apenas a primeira reserva confirmada fica registrada.

Não coloque dados pessoais desnecessários. O sistema registra o nome informado e horário da reserva.
