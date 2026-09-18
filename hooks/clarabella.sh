#!/usr/bin/env bash
if grep -qiE 'clarabel+a'; then
  echo "El usuario le está hablando a Clarabella, la vaca del plugin clarabella. Invocá la skill clarabella:clarabella con la herramienta Skill antes de responder, y seguí sus instrucciones para derivar el pedido."
fi
exit 0
