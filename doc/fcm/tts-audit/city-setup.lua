-- Funcion principal
rotacion = {{0,0,0},{0,90,0},{0,180,0},{0,270,0}}

function onLoad(save_state)
  self.shuffle()

  button_params={}
  button_params.position={25,0.5,-3}
  button_params.width=4000
  button_params.height=500
  button_params.font_size=400
  button_params.function_owner = self
  button_params.label="> 3 Players <"
  button_params.click_function="Setup_tres_jugadores"
  self.createButton(button_params)

  button_params.position={25,0.5,-5}
  button_params.label="> 2 Players <"
  button_params.click_function="Setup_dos_jugadores"
  self.createButton(button_params)


  button_params.position={25,0.5,-1}
  button_params.label="> 4 Players <"
  button_params.click_function="Setup_cuatro_jugadores"
  self.createButton(button_params)

  button_params.position={25,0.5,1}
  button_params.label="> 5 Players <"
  button_params.click_function="Setup_cinco_jugadores"
  self.createButton(button_params)
end


function Setup_dos_jugadores()
  limpiar()
  params1={position={-0.5,1,-15.75}}
  bolsa=getObjectFromGUID('3818a8').clone(params1)
  bolsa.shuffle()
  params={callback="bloquear", callback_owner=self}
  iniX = -9
  coordX = iniX
  incX = 6.5
  iniZ = -9
  incZ = incX
  coordZ = iniZ
  for i=1,9 do
    params.position={coordX,1,coordZ}
    params.rotation=rotacion[math.random(4)]
    bolsa.takeObject(params)
    if(i%3 == 0) then
      coordX = iniX
      coordZ = coordZ + incZ
    else
      coordX = coordX + incX
    end
  end
  bolsa.destruct()
end

function Setup_tres_jugadores()
  limpiar()
  params1={position={-0.5,1,-15.75}}
  bolsa=getObjectFromGUID('3818a8').clone(params1)
  bolsa.shuffle()
  params={callback="bloquear", callback_owner=self}
  iniX = -9
  coordX = iniX
  incX = 6.5
  iniZ = -9
  incZ = incX
  coordZ = iniZ
  for i=1,12 do
    params.position={coordX,1,coordZ}
    params.rotation=rotacion[math.random(4)]
    bolsa.takeObject(params)
    if(i%3 == 0) then
      coordX = iniX
      coordZ = coordZ + incZ
    else
      coordX = coordX + incX
    end
  end
  bolsa.destruct()
end

function Setup_cuatro_jugadores()
  limpiar()
  params1={position={-0.5,1,-15.75}}
  bolsa=getObjectFromGUID('3818a8').clone(params1)
  bolsa.shuffle()
  params={callback="bloquear", callback_owner=self}
  iniX = -11
  coordX = iniX
  incX = 6.5
  iniZ = -9
  incZ = incX
  coordZ = iniZ
  for i=1,16 do
    params.position={coordX,1,coordZ}
    params.rotation=rotacion[math.random(4)]
    item=bolsa.takeObject(params)
    if(i%4 == 0) then
      coordX = iniX
      coordZ = coordZ + incZ
    else
      coordX = coordX + incX
    end
  end
  bolsa.destruct()
end

function Setup_cinco_jugadores()
  limpiar()
  params1={position={-0.5,1,-15.75}}
  bolsa=getObjectFromGUID('3818a8').clone(params1)
  bolsa.shuffle()
  params={callback="bloquear", callback_owner=self}
  iniX = -11
  coordX = iniX
  incX = 6.5
  iniZ = -11
  incZ = incX
  coordZ = iniZ
  for i=1,20 do
    params.position={coordX,1,coordZ}
    params.rotation=rotacion[math.random(4)]
    bolsa.takeObject(params)
    if(i%4 == 0) then
      coordX = iniX
      coordZ = coordZ + incZ
    else
      coordX = coordX + incX
    end
  end
  bolsa.destruct()
end

function limpiar()
  objetos_a_borrar = getObjectFromGUID('b5c091').getObjects()
  local c = 0
  for k,v in pairs(objetos_a_borrar ) do
    c = c+1
  end
  if (c>0) then
    for k,v in pairs(objetos_a_borrar ) do
      v.destruct()
    end
  end
end

function bloquear(c)
  c.lock()
end
