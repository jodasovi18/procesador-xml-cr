import { useState } from 'react';
import { Stack, Title, Text, Table, Badge, Group } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { notifications } from '@mantine/notifications';
import { useIngestaLote, ResultadoArchivo, LoteResponse } from '../api/hooks';
import { ApiError } from '../api/client';

const COLOR: Record<ResultadoArchivo['estado'], string> = {
  nuevo: 'teal',
  actualizado: 'blue',
  omitido: 'gray',
  error: 'red',
};

export function SubidaPage() {
  const ingesta = useIngestaLote();
  const [resumen, setResumen] = useState<LoteResponse | null>(null);

  async function onDrop(files: File[]) {
    try {
      const res = await ingesta.mutateAsync(files);
      setResumen(res);
      notifications.show({
        color: res.errores > 0 ? 'orange' : 'teal',
        message: `Procesados ${res.total}: ${res.nuevos} nuevos, ${res.actualizados} actualizados, ${res.omitidos} omitidos, ${res.errores} con error`,
      });
    } catch (e) {
      notifications.show({
        color: 'red',
        message: e instanceof ApiError ? e.detail : 'Error al subir',
      });
    }
  }

  return (
    <Stack>
      <Title order={2}>Subir comprobantes</Title>
      <Dropzone
        onDrop={onDrop}
        loading={ingesta.isPending}
        accept={['text/xml', 'application/xml', 'application/zip', 'application/x-zip-compressed']}
      >
        <Text ta="center" p="xl">
          Arrastrá archivos XML o ZIP, o hacé clic para elegir
        </Text>
      </Dropzone>
      {resumen && (
        <>
          <Group>
            <Badge color="teal">{resumen.nuevos} nuevos</Badge>
            <Badge color="blue">{resumen.actualizados} actualizados</Badge>
            <Badge color="gray">{resumen.omitidos} omitidos</Badge>
            <Badge color="red">{resumen.errores} con error</Badge>
          </Group>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Archivo</Table.Th>
                <Table.Th>Estado</Table.Th>
                <Table.Th>Motivo</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {resumen.archivos.map((r) => (
                <Table.Tr key={r.archivo}>
                  <Table.Td>{r.archivo}</Table.Td>
                  <Table.Td>
                    <Badge color={COLOR[r.estado]}>{r.estado}</Badge>
                  </Table.Td>
                  <Table.Td>{r.motivo ?? ''}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  );
}
