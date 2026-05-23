namespace VehicleLogger.Api.Dtos;

/// GPS-снимок, отправляемый устройством вместе с пакетом телеметрии.
/// Все поля nullable — присутствуют, только если фикс был свежим (≤10 с) на момент сборки пакета.
public class GpsData
{
    /// Широта, градусы (WGS-84).
    public double? Lat { get; set; }
    /// Долгота, градусы (WGS-84).
    public double? Lng { get; set; }
    /// Высота над уровнем моря, метры.
    public double? Alt { get; set; }
    /// Скорость по GPS, км/ч.
    public double? Speed { get; set; }
    /// Курс движения, градусы 0..359.
    public double? Course { get; set; }
    /// Количество спутников в решении.
    public int? Sats { get; set; }
    /// Тип фикса: 0=нет, 1=2D, 2=3D.
    public int? Fix { get; set; }
}