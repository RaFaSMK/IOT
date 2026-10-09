<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import {court, fresh, canOperate, deviceState} from '@/services/court'
import DataChart from './DataChart.vue'
const emit = defineEmits<{command: [identifier: string, action: string, on?: boolean]}>()
const container = ref<HTMLDivElement>()
const selected = ref('compressor_01')
const failure = ref('')
const device = computed(() => court.devices.find(item => item.id === selected.value))
const chartId = computed(() => selected.value === 'compressor_01' || selected.value === 'cooling' ? 'compressor_vibration' : selected.value)
const value = computed(() => {
  const measured = court.telemetry?.sensors[selected.value]
  if (measured !== undefined) return measured.toLocaleString('pt-BR', {maximumFractionDigits: 2}) + ' ' + (device.value?.unit || '')
  const state = court.telemetry?.actuators[selected.value]
  if (state !== undefined) return state ? 'Ligado' : 'Desligado'
  return selected.value === 'compressor_01' ? (court.telemetry?.actuators.cooling ? 'Em operação' : 'Desligado') : '—'
})
const positions: Record<string, [number, number, number]> = {
  ambient_temperature: [-6, 1.7, -6], humidity: [-5, 1.7, -6], luminosity: [-4, 1.7, -6],
  water_temperature: [7.1, 2.2, 2.6], compressor_temperature: [8.8, .8, 2.5], compressor_current: [8.8, .8, 3.3], compressor_vibration: [8.8, .8, 4.1],
  compressor_01: [7.4, .7, 3.4], cooling: [7.4, 1.7, 3.4], floodlights: [-5, 4.8, 5.6], highlight_button: [1, 1.2, 5.5], simulator: [-7, .8, -6],
}
const colors: Record<string, number> = {normal: 0x38d9ae, warning: 0xf2bd65, critical: 0xf87171, no_data: 0x62748a}
let dispose = () => {}

onMounted(() => {
  const host = container.value
  if (!host) return
  try {
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x17263d)
    const renderer = new THREE.WebGLRenderer({antialias: true})
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    host.appendChild(renderer.domElement)
    const camera = new THREE.PerspectiveCamera(45, 1, .1, 100)
    camera.position.set(20, 17, 23)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(1, 0, 0)
    controls.enableDamping = true
    controls.maxPolarAngle = Math.PI / 2.08
    controls.minDistance = 8; controls.maxDistance = 45
    const ambient = new THREE.AmbientLight(0xe7f4ff, .5)
    scene.add(ambient)
    const sun = new THREE.DirectionalLight(0xffe4af, 1.5)
    sun.position.set(8, 15, 5); sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024)
    sun.shadow.camera.left = -20; sun.shadow.camera.right = 20; sun.shadow.camera.top = 20; sun.shadow.camera.bottom = -20
    scene.add(sun)
    const objects: THREE.Object3D[] = []
    const materials: THREE.Material[] = []
    const textures: THREE.Texture[] = []
    const markers: Record<string, THREE.Mesh> = {}
    function material(color: number) {const m = new THREE.MeshStandardMaterial({color, roughness: .8}); materials.push(m); return m}
    function box(w: number,h: number,d: number,x: number,y: number,z: number,color: number, parent: THREE.Object3D = scene) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material(color)); mesh.position.set(x,y,z); mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh
    }
    function label(text: string, x: number, y: number, z: number) {
      const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 80
      const context = canvas.getContext('2d')!
      context.fillStyle = '#0c1724dd'; context.fillRect(0,0,512,80)
      context.font = '28px sans-serif'; context.textAlign = 'center'; context.fillStyle = '#e2e8f0'; context.fillText(text,256,50)
      const texture = new THREE.CanvasTexture(canvas); textures.push(texture)
      const m = new THREE.SpriteMaterial({map: texture, depthTest: false}); materials.push(m)
      const sprite = new THREE.Sprite(m); sprite.position.set(x,y,z); sprite.scale.set(3.2,.5,1); scene.add(sprite)
    }
    box(30,.2,24,0,-.18,0,0x1a3534)
    box(9,.15,17,0,0,0,0xcab98f)
    // Linhas, rede e postes da quadra.
    for (const x of [-4,4]) box(.08,.03,16,x,.11,0,0xffffff)
    for (const z of [-8,8]) box(8,.03,.08,0,.11,z,0xffffff)
    for (const x of [-4.7,4.7]) box(.12,2.4,.12,x,1.2,0,0xced4dc)
    const net = new THREE.Mesh(new THREE.PlaneGeometry(9.4,1.2,24,4),new THREE.MeshBasicMaterial({color:0xd8e4ee,wireframe:true,transparent:true,opacity:.65,side:THREE.DoubleSide})); net.position.set(0,1.7,0); scene.add(net)
    label('QUADRA · BEACH TENNIS',0,.8,9)
    // Carcaça aberta para o compressor e os sensores permanecerem visíveis.
    box(2.2,2.7,.12,7.4,1.35,4.55,0xd1dbe1)
    box(.14,2.7,2.4,6.37,1.35,3.4,0xd1dbe1)
    box(2.2,.14,2.4,7.4,2.63,3.4,0xd1dbe1)
    box(1.8,.7,.12,7.4,2.2,2.14,0x1c5866)
    label('BEBEDOURO',7.4,3.4,3.4)
    const compressor = new THREE.Group(); compressor.position.set(...positions.compressor_01!); compressor.userData.device = 'compressor_01'; scene.add(compressor)
    const casing = box(1.15,1,1.15,0,0,0,0x425d70,compressor)
    const rotor = box(.9,.06,.1,0,.57,0,0x38d9ae,compressor)
    casing.userData.device = 'compressor_01'; objects.push(casing)
    const water = box(1.6,.4,.7,7.4,1.7,2.5,0x268fb0)
    const lamp = box(1.2,.4,.6,-5,4.8,5.6,0xf2eab9)
    lamp.userData.device = 'floodlights'; objects.push(lamp)
    box(.16,4.7,.16,-5,2.35,5.6,0x526577)
    const flood = new THREE.PointLight(0xffedc0,0,25,1.5); flood.position.set(-5,4.6,5.6); scene.add(flood)
    for (const [id, position] of Object.entries(positions)) {
      const marker = new THREE.Mesh(new THREE.SphereGeometry(.17,10,8),material(0x62748a)); marker.position.set(...position); marker.userData.device = id; scene.add(marker); markers[id] = marker; objects.push(marker)
    }
    for (const [id, position] of Object.entries(positions)) {
      if (['compressor_01','cooling','floodlights','water_temperature','simulator'].includes(id)) continue
      const title = court.devices.find(item => item.id === id)?.name || id
      label(title,position[0],position[1] + .7,position[2])
    }
    // Nuvens: um segundo elemento ambiental cuja opacidade acompanha a umidade.
    const cloudMaterial = new THREE.MeshStandardMaterial({color:0xc7d8e5,transparent:true,opacity:0}); materials.push(cloudMaterial)
    const clouds = new THREE.InstancedMesh(new THREE.SphereGeometry(1,10,8),cloudMaterial,8)
    for (let i=0;i<8;i++) {const matrix = new THREE.Matrix4().compose(new THREE.Vector3(-8 + i*2,7.5 + (i%2)*.5,-7),new THREE.Quaternion(),new THREE.Vector3(1.4,.5,.8)); clouds.setMatrixAt(i,matrix)}
    scene.add(clouds)
    function resize() {const width = host!.clientWidth; const height = host!.clientHeight; renderer.setSize(width,height); camera.aspect = width/height; camera.updateProjectionMatrix()}
    const observer = new ResizeObserver(resize); observer.observe(host); resize()
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let downX=0,downY=0
    function pointerDown(event: PointerEvent) {downX=event.clientX; downY=event.clientY}
    function click(event: PointerEvent) {
      if (Math.hypot(event.clientX-downX,event.clientY-downY)>5) return
      const rect=renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1); raycaster.setFromCamera(pointer,camera)
      const hit=raycaster.intersectObjects(objects,false)[0]; if (hit) selected.value=hit.object.userData.device
    }
    renderer.domElement.addEventListener('pointerdown',pointerDown)
    renderer.domElement.addEventListener('pointerup',click)
    let frame=0; let last=performance.now(); let phase=0
    function animate(current: number) {
      frame=requestAnimationFrame(animate)
      const dt=Math.min((current-last)/1000,.1); last=current
      controls.update()
      for (const [id, marker] of Object.entries(markers)) (marker.material as THREE.MeshStandardMaterial).color.setHex(colors[deviceState(id)]!)
      if (fresh.value && court.telemetry) {
        const readings=court.telemetry.sensors; const actuators=court.telemetry.actuators
        const daylight=THREE.MathUtils.clamp((readings.luminosity || 0)/60000,0,1)
        scene.background=new THREE.Color(0x101a30).lerp(new THREE.Color(0x86b7d2),daylight)
        sun.intensity=.15+daylight*1.8; ambient.intensity=.3+daylight*.4
        cloudMaterial.opacity=THREE.MathUtils.clamp(((readings.humidity || 0)-25)/100,0,.7)
        flood.intensity=actuators.floodlights ? 70 : 0
        const lampMaterial=lamp.material as THREE.MeshStandardMaterial; lampMaterial.emissive.setHex(actuators.floodlights ? 0xffe3a0 : 0x000000); lampMaterial.emissiveIntensity=actuators.floodlights ? 1 : 0
        const waterMaterial=water.material as THREE.MeshStandardMaterial; waterMaterial.color.setHSL(.55-THREE.MathUtils.clamp((readings.water_temperature || 10)-10,0,25)/70,.7,.4)
        if (actuators.cooling) {
          phase+=dt; rotor.rotation.y+=dt*8
          const amplitude=Math.min((readings.compressor_vibration || 0)*.012,.15)
          compressor.position.x=7.4+Math.sin(phase*35)*amplitude
        } else { compressor.position.x=7.4 }
        (casing.material as THREE.MeshStandardMaterial).color.setHex(colors[deviceState('compressor_01')]!)
      }
      renderer.render(scene,camera)
    }
    frame=requestAnimationFrame(animate)
    dispose=() => {cancelAnimationFrame(frame); observer.disconnect(); controls.dispose(); renderer.domElement.removeEventListener('pointerdown',pointerDown); renderer.domElement.removeEventListener('pointerup',click); scene.traverse(object => {if (object instanceof THREE.Mesh) {object.geometry.dispose(); const m=object.material; (Array.isArray(m) ? m : [m]).forEach(item=>item.dispose())}}); materials.forEach(m=>m.dispose()); textures.forEach(t=>t.dispose()); renderer.dispose(); renderer.domElement.remove()}
  } catch {failure.value='Não foi possível iniciar a cena 3D. Verifique se o navegador oferece WebGL.'}
})
onUnmounted(() => dispose())
</script>

<template>
  <section class="twin-layout">
    <div class="scene-panel"><div class="scene-label"><strong>Quadra ao vivo</strong><span>{{fresh ? 'Clique nos equipamentos para inspecionar' : 'Sem dados · animações pausadas'}}</span></div><p v-if="failure" role="alert">{{failure}}</p><div ref="container" class="scene-container"></div><div class="legend"><span class="normal">● Normal</span><span class="warning">● Atenção</span><span class="critical">● Crítico</span><span>● Sem dados</span></div></div>
    <aside class="item-panel"><label>Inspecionar<select v-model="selected"><option v-for="item in court.devices.filter(item => positions[item.id])" :key="item.id" :value="item.id">{{item.name}}</option></select></label><h2>{{device?.name || selected}}</h2><code>{{selected}}</code><strong class="reading">{{value}}</strong><p>{{fresh ? 'Última leitura recebida' : 'Leitura antiga · sem dados recentes'}}</p><DataChart :points="court.history[chartId] || []" :label="device?.unit" /><h3>Saúde do compressor</h3><p>{{fresh && court.prediction?.status === 'ready' ? court.prediction.health?.toFixed(1) + '/100 · ' + court.prediction.rul_hours?.toFixed(1) + ' h restantes' : 'Previsão indisponível'}}</p><div v-if="canOperate && (selected === 'floodlights' || selected === 'cooling')" class="commands"><button @click="emit('command', selected, 'set', true)">Ligar</button><button @click="emit('command', selected, 'set', false)">Desligar</button><small v-if="selected === 'cooling'">A regra automática pode alterar a refrigeração conforme a temperatura da água.</small></div><button v-if="canOperate && selected === 'highlight_button'" @click="emit('command', selected, 'highlight')">Registrar highlight</button></aside>
  </section>
</template>
<style scoped>
.twin-layout{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:20px}.scene-panel,.item-panel{background:#101c2a;border:1px solid #243346;border-radius:14px;overflow:hidden}.scene-panel{position:relative}.scene-container{height:590px;min-height:400px;width:100%}.scene-label{position:absolute;top:20px;left:20px;display:flex;flex-direction:column;gap:5px;padding:12px;background:#0b1521dd;border-radius:8px;pointer-events:none}.scene-label strong{font-size:14px}.scene-label span{font-size:11px;color:#9eb0c0}.legend{display:flex;gap:15px;padding:12px 20px;font-size:11px;color:#7890a3}.normal{color:#38d9ae}.warning{color:#f2bd65}.critical{color:#f87171}.item-panel{padding:22px}.item-panel h2{font-size:18px;margin:20px 0 8px}.item-panel h3{font-size:14px;margin:15px 0 8px}.item-panel p{font-size:12px;color:#91a5b7}.item-panel code{font-size:10px;color:#6f91a4}.reading{display:block;font-size:26px;margin:22px 0 6px}.item-panel label{display:flex;flex-direction:column;gap:8px;font-size:11px;color:#91a5b7}.item-panel select{background:#0b1521;border:1px solid #30455b;color:#d6e4ef;padding:9px;border-radius:7px;width:100%}.commands{display:flex;flex-wrap:wrap;gap:10px;margin-top:15px}button{background:#38d9ae;border:0;color:#09261e;padding:10px 14px;border-radius:7px;font-weight:650;cursor:pointer}.commands small{color:#91a5b7;font-size:11px;width:100%}@media(max-width:1050px){.twin-layout{grid-template-columns:1fr}.scene-container{height:470px}.item-panel{max-width:100%}}@media(max-width:650px){.scene-container{height:400px}.legend{flex-wrap:wrap}}
</style>
